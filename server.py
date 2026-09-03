from enlace import *
from utils import *

import time
import os

serialName = "COM3"
SERVER_FOLDER = "arquivos_server"
TIMEOUT = 2
MAX_RETRIES = 5

# FUNÇÕES AUXILIARES

def receive_packet(com1):
    header = com1.rx.getNData(HEADER_SIZE)
    header_info = parse_header(header)
    payload_size = header_info["payload_size"]
    payload = b''
    if payload_size > 0:
        payload = com1.rx.getNData(payload_size)
    eop = com1.rx.getNData(len(EOP))
    packet = header + payload + eop
    return packet, header_info, payload

def receive_packet_timeout(com1):
    start_time = time.time()
    # Espera o header chegar
    while com1.rx.getBufferLen() < HEADER_SIZE:
        if time.time() - start_time >= TIMEOUT:
            return None, None, None
        time.sleep(0.05)
    header = com1.rx.getNData(HEADER_SIZE)
    header_info = parse_header(header)
    payload_size = header_info["payload_size"]
    # Espera o payload chegar
    while com1.rx.getBufferLen() < payload_size:
        if time.time() - start_time >= TIMEOUT:
            com1.rx.clearBuffer()
            return None, None, None
        time.sleep(0.05)
    payload = b''
    if payload_size > 0:
        payload = com1.rx.getNData(payload_size)
    # Espera o EOP
    while com1.rx.getBufferLen() < len(EOP):
        if time.time() - start_time >= TIMEOUT:
            com1.rx.clearBuffer()
            return None, None, None
        time.sleep(0.05)
    eop = com1.rx.getNData(len(EOP))
    packet = header + payload + eop
    return packet, header_info, payload

def get_available_files():
    files = os.listdir(SERVER_FOLDER)
    available_files = []
    for file_name in files:
        path = os.path.join(SERVER_FOLDER, file_name)
        if os.path.isfile(path):
            available_files.append(file_name)
    return available_files

def build_file_list_payload(files):
    text = ""
    for i in range(len(files)):
        text += str(i + 1)
        text += ":"
        text += files[i]
        text += "\n"
    return text.encode()

# MAIN

def main():
    try:
        print("========================================")
        print("          SERVIDOR INICIADO")
        print("========================================")

        com1 = enlace(serialName)
        com1.enable()
        print("Comunicação serial aberta.")
        print("Abriu a comunicação")
        print("esperando 1 byte de sacrifício")
        rxBuffer, nRx = com1.getData(1)
        com1.rx.clearBuffer()
        time.sleep(.1)

        # LISTA DE ARQUIVOS DISPONÍVEIS
        available_files = get_available_files()

        print()
        print("Arquivos disponíveis no servidor:")

        for i in range(len(available_files)):
            print("[" + str(i + 1) + "]", available_files[i])

        # HANDSHAKE
        print()
        print("----------------------------------------")
        print("Aguardando HANDSHAKE...")
        print("----------------------------------------")

        packet, header, payload = receive_packet(com1)

        if header["msg_type"] == HANDSHAKE:
            print("HANDSHAKE recebido do cliente.")

            file_list_payload = build_file_list_payload(available_files)
            file_list_packet = build_packet(msg_type=FILE_LIST, payload=file_list_payload)
            send_packet(com1, file_list_packet)
            print("Lista de arquivos enviada ao cliente.")
        else:
            print("Mensagem recebida não era HANDSHAKE.")
            com1.disable()
            return

        # ESCOLHA DOS ARQUIVOS
        selected_files = []
        selecting = True

        print()
        print("----------------------------------------")
        print("Aguardando seleção de arquivos...")
        print("----------------------------------------")
        while selecting:
            packet, header, payload = receive_packet(com1)
            msg_type = header["msg_type"]

            # CLIENTE ESCOLHEU UM ARQUIVO
            if msg_type == FILE_REQUEST:
                file_id = header["file_id"]
                if file_id >= 1 and file_id <= len(available_files):
                    file_name = available_files[file_id - 1]
                    if file_name not in selected_files:
                        selected_files.append(file_name)
                        print()
                        print("Arquivo escolhido:", file_name)
                    else:
                        print()
                        print("Arquivo já havia sido escolhido:", file_name)

                    confirmation_payload = file_name.encode()
                    confirmation = build_packet(msg_type=FILE_SELECTED, payload=confirmation_payload, file_id=file_id)
                    send_packet(com1, confirmation)
                    print("Confirmação enviada ao cliente.")
                else:
                    print("Cliente solicitou um ID inválido:", file_id)

            # CLIENTE TERMINOU A ESCOLHA
            elif msg_type == FINISH_SELECTION:
                print()
                print("Cliente terminou a seleção.")
                selecting = False

        # MOSTRA ARQUIVOS SELECIONADOS
        print()
        print("----------------------------------------")
        print("Arquivos selecionados:")
        print("----------------------------------------")
        for file_name in selected_files:
            print("-", file_name)

        # PREPARAÇÃO DOS ARQUIVOS
        files_to_send = []
        file_id = 1
        for file_name in selected_files:
            path = os.path.join(SERVER_FOLDER,file_name)
            file = open(path,"rb")
            data = file.read()
            file.close()
            packets = fragment_data(data)
            file_info = {
                "id": file_id,
                "name": file_name,
                "data": data,
                "packets": packets,
                "next_packet": 0
            }
            files_to_send.append(file_info)
            print()
            print("Arquivo:", file_name)
            print("Tamanho:", len(data), "bytes")
            print("Quantidade de pacotes:", len(packets))
            file_id += 1

        # AVISA QUE A TRANSMISSÃO VAI COMEÇAR
        print()
        print("----------------------------------------")
        print("Iniciando transmissão...")
        print("----------------------------------------")

        start_packet = build_packet(msg_type=START_TRANSFER)
        send_packet(com1, start_packet)

        # TRANSMISSÃO INTERCALADA
        transmitting = True
        transmitting_aborted = False

        while transmitting and not transmitting_aborted:
            transmitting = False
            # Percorre todos os arquivos uma vez
            for file_info in files_to_send:
                packets = file_info["packets"]
                next_packet = file_info["next_packet"]
                # Verifica se esse arquivo ainda tem
                # algum pacote para transmitir
                if next_packet < len(packets):
                    transmitting = True
                    payload = packets[next_packet]
                    packet_number = next_packet + 1
                    total_packets = len(packets)

                    # MONTA PACOTE DE DADOS
                    packet = build_packet(msg_type=DATA, payload=payload, file_id=file_info["id"], packet_number=packet_number, total_packets=total_packets)
                    print()
                    print("Enviando arquivo", file_info["id"], "-", file_info["name"])
                    print("Pacote", packet_number, "de", total_packets)
                    print("Payload:", len(payload), "bytes")
                    send_packet(com1, packet)

                    # ESPERA ACK
                    print("Aguardando ACK...")
                    ack_recebido = False
                    tentativa = 1
                    while tentativa <= MAX_RETRIES and not ack_recebido:
                        ack_packet, ack_header, ack_payload = receive_packet_timeout(com1)

                        # TIMEOUT
                        if ack_header is None:
                            print()
                            print("[TIMEOUT] ACK não recebido.")
                            print("Retransmitindo pacote...")
                            send_packet(com1, packet)
                            tentativa += 1
                            continue

                        # RECEBEU ALGUMA COISA
                        if ack_header["msg_type"] == ACK:
                            if (ack_header["file_id"] == file_info["id"] and ack_header["ack_number"] == packet_number):
                                print()
                                print("ACK recebido:", "arquivo",file_info["id"],"pacote",packet_number)
                                ack_recebido = True
                                file_info["next_packet"] += 1

                                # PAUSA
                                if ack_header["control"] == PAUSE:
                                    print()
                                    print("========================================")
                                    print("        TRANSMISSÃO PAUSADA")
                                    print("========================================")
                                    print("Aguardando comando do cliente...")
                                    paused = True
                                    while paused:
                                        command_packet, command_header, command_payload = receive_packet(com1)
                                        # CONTINUAR
                                        if command_header["control"] == CONTINUE:
                                            paused = False
                                            print()
                                            print("========================================")
                                            print("       TRANSMISSÃO CONTINUADA")
                                            print("========================================")
                                        elif command_header["control"] == RESTART:
                                            print()
                                            print("========================================")
                                            print("       REINICIANDO TRANSMISSÃO")
                                            print("========================================")
                                            for arquivo in files_to_send:
                                                arquivo["next_packet"] = 0
                                            paused = False
                                        elif command_header["control"] == ABORT:
                                            print()
                                            print("========================================")
                                            print("       TRANSMISSÃO ABORTADA")
                                            print("========================================")
                                            paused = False
                                            transmitting_aborted = True

                                elif ack_header["control"] == RESTART:
                                    print()
                                    print("========================================")
                                    print("       REINICIANDO TRANSMISSÃO")
                                    print("========================================")
                                    for arquivo in files_to_send:
                                        arquivo["next_packet"] = 0

                                elif ack_header["control"] == ABORT:
                                    print()
                                    print("========================================")
                                    print("       TRANSMISSÃO ABORTADA")
                                    print("========================================")
                                    transmitting_aborted = True

                            else:
                                print("ACK recebido, mas não corresponde","ao pacote enviado.")
                                tentativa += 1
                        else:
                            print("Servidor esperava ACK, mas recebeu:", message_name(ack_header["msg_type"]))
                            tentativa += 1

                    if transmitting_aborted:
                        break

                    # VERIFICA SE ESGOTOU AS TENTATIVAS
                    if not ack_recebido:
                        print()
                        print("Não foi possível receber o ACK.")
                        print("Número máximo de tentativas atingido.")
                        break

            if transmitting_aborted:
                break

        if not transmitting_aborted:
            # FINALIZA CADA ARQUIVO
            for file_info in files_to_send:
                end_file_packet = build_packet(msg_type=END_FILE, file_id=file_info["id"])
                send_packet(com1, end_file_packet)
                print()
                print("Arquivo", file_info["name"], "transmitido completamente.")

        # FINALIZA TODA A TRANSMISSÃO
            end_packet = build_packet(msg_type=END_TRANSFER)
            send_packet(com1, end_packet)

        print()
        print("========================================")
        print("       TRANSMISSÃO FINALIZADA")
        print("========================================")

        print()
        print("Resumo:")

        for file_info in files_to_send:
            print()
            print("Arquivo:", file_info["name"])

            print("Tamanho:", len(file_info["data"]), "bytes")

            print("Pacotes enviados:", len(file_info["packets"]))
        print()
        print("Servidor encerrado.")
        com1.disable()

    except Exception as erro:
        print()
        print("Ops! Ocorreu um erro no servidor.")
        print(erro)
        com1.disable()

if __name__ == "__main__":
    main()