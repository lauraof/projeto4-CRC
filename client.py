from enlace import *
from utils import *

import time
import os
import msvcrt

serialName = "COM5"
pasta_cliente = "arquivos_client"

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

def parse_file_list(payload):
    text = payload.decode()
    lines = text.split("\n")
    files = []
    for line in lines:
        if line != "":
            parts = line.split(":")
            file_name = parts[1]
            files.append(file_name)
    return files

def check_keyboard():
    if msvcrt.kbhit():
        tecla = msvcrt.getch().decode().lower()
        return tecla
    return None


def main():
    try:

        print("========================================")
        print("           CLIENTE INICIADO")
        print("========================================")

        com1 = enlace(serialName)
        com1.enable()
        print("Comunicação serial aberta.")
        # bit de sacrifício
        time.sleep(.2)
        com1.sendData(b'00')
        time.sleep(1)
        print("bit de sacrifício enviado")
        com1.rx.clearBuffer()
        print("----------------------------------------")
        print("Enviando HANDSHAKE ao servidor...")
        print("----------------------------------------")

        handshake_packet = build_packet(msg_type=HANDSHAKE)
        send_packet(com1, handshake_packet)

        print("HANDSHAKE enviado.")
        print("Aguardando lista de arquivos...")

        # RECEBE LISTA DE ARQUIVOS
        packet, header, payload = receive_packet(com1)

        if header["msg_type"] == FILE_LIST:
            print()
            print("Lista de arquivos recebida!")
            available_files = parse_file_list(payload)
        else:
            print("Resposta inesperada do servidor.")
            com1.disable()
            return

        # MOSTRA ARQUIVOS DISPONÍVEIS

        print()
        print("========================================")
        print("       ARQUIVOS DISPONÍVEIS")
        print("========================================")

        for i in range(len(available_files)):
            print(
                "[" + str(i + 1) + "]",
                available_files[i]
            )

        # SELEÇÃO DOS ARQUIVOS
        selected_files = []
        selecting = True
        while selecting:
            print()
            option = int(
                input("Digite o número do arquivo desejado: ")
            )
            # Verifica se o número existe
            if option >= 1 and option <= len(available_files):
                file_name = available_files[option - 1]
                # Evita escolher o mesmo arquivo novamente
                if file_name in selected_files:
                    print()
                    print("Esse arquivo já foi selecionado.")
                else:
                    # ENVIA FILE_REQUEST
                    request_packet = build_packet(msg_type=FILE_REQUEST, file_id=option)
                    send_packet(com1, request_packet)
                    print()
                    print("Solicitação enviada:", file_name)
                    # ESPERA CONFIRMAÇÃO
                    packet, header, payload = receive_packet(com1)
                    if header["msg_type"] == FILE_SELECTED:
                        confirmed_file = payload.decode()
                        selected_files.append(confirmed_file)
                        print()
                        print("Servidor confirmou:", confirmed_file)
                    else:
                        print("Servidor enviou uma resposta inesperada:", message_name(header["msg_type"]))
            else:
                print()
                print("Número de arquivo inválido.")
            # SÓ PODE TERMINAR DEPOIS DE 2 ARQUIVOS
            if len(selected_files) >= 2:
                print()
                print("Arquivos selecionados:")
                for file_name in selected_files:
                    print("-", file_name)
                print()
                answer = input("Deseja adicionar outro arquivo? (s/n): ")
                if answer == "n" or answer == "N":
                    selecting = False
            else:
                print()
                print("Você precisa selecionar pelo menos 2 arquivos.")

        # AVISA QUE TERMINOU A SELEÇÃO
        finish_packet = build_packet(msg_type=FINISH_SELECTION)
        send_packet(com1, finish_packet)
        print()
        print("----------------------------------------")
        print("Seleção finalizada.")
        print("----------------------------------------")
        print()
        print("Arquivos escolhidos:")
        for file_name in selected_files:
            print("-", file_name)

        # ESPERA START_TRANSFER
        print()
        print("Aguardando início da transmissão...")
        packet, header, payload = receive_packet(com1)
        if header["msg_type"] == START_TRANSFER:
            print()
            print("Servidor iniciou a transmissão!")
            print()
            print("----------------------------------------")
            print("CONTROLES DA TRANSMISSÃO")
            print("P = pausar")
            print("C = continuar após pausa")
            print("R = reiniciar desde o começo")
            print("A = abortar")
            print("----------------------------------------")
        else:
            print("Mensagem inesperada:", message_name(header["msg_type"]))
            com1.disable()
            return

        # PREPARA ESTRUTURA PARA RECEBER OS ARQUIVOS
        received_files = []
        for i in range(len(selected_files)):
            file_info = {
                "id": i + 1,
                "name": selected_files[i],
                "data": b'',
                "received_packets": 0,
                "total_packets": 0,
                "last_packet": 0    
            }
            received_files.append(file_info)

        # RECEPÇÃO DOS PACOTES
        transmission_finished = False
        transmission_aborted = False
        print()
        print("========================================")
        print("      RECEBENDO ARQUIVOS")
        print("========================================")
        while not transmission_finished:
            packet, header, payload = receive_packet(com1)
            msg_type = header["msg_type"]
            # PACOTE DE DADOS
            if msg_type == DATA:
                file_id = header["file_id"]
                packet_number = header["packet_number"]
                total_packets = header["total_packets"]
                payload_size = header["payload_size"]
                # file_id começa em 1
                file_info = received_files[file_id - 1]
                print()
                print("----------------------------------------")
                print("Recebendo arquivo:", file_info["name"])
                print("Pacote:", packet_number, "de", total_packets)
                print("Payload:", payload_size, "bytes")
                # GUARDA OS DADOS
                # VERIFICA SE É UM PACOTE NOVO
                if packet_number > file_info["last_packet"]:
                    file_info["data"] += payload
                    file_info["received_packets"] += 1
                    file_info["total_packets"] = total_packets
                    file_info["last_packet"] = packet_number
                    print('Pacote novo recebido.')
                else:
                    print('Pacote duplicado recebido.')
                    print('Os dados não serão adicionados novamente.')

                # VERIFICA TECLA DE CONTROLE
                tecla = check_keyboard()
                control = NORMAL
                if tecla == "p":
                    control = PAUSE
                elif tecla == "r":
                    control = RESTART
                elif tecla == "a":
                    control = ABORT
                
                # ENVIA ACK + COMANDO DE CONTROLE
                ack_packet = build_packet(msg_type=ACK, file_id=file_id, ack_number=packet_number, control=control)
                send_packet(com1, ack_packet)
                print("ACK enviado:", "arquivo", file_id, "pacote", packet_number)

                # PAUSA
                if control == PAUSE:
                    print()
                    print("========================================")
                    print("        TRANSMISSÃO PAUSADA")
                    print("========================================")
                    print("Pressione C para continuar.")
                    print("Pressione R para reiniciar.")
                    print("Pressione A para abortar.")
                    paused = True
                    while paused:
                        if msvcrt.kbhit():
                            tecla = msvcrt.getch().decode().lower()
                            # CONTINUAR
                            if tecla == "c":
                                command_packet = build_packet(msg_type=ACK, control=CONTINUE)
                                send_packet(com1, command_packet)
                                paused = False
                                print()
                                print("Transmissão continuada.")

                            # REINICIAR
                            elif tecla == "r":
                                command_packet = build_packet(msg_type=ACK, control=RESTART)
                                send_packet(com1, command_packet)
                                # Apaga tudo que já havia sido recebido
                                for arquivo in received_files:
                                    arquivo["data"] = b''
                                    arquivo["received_packets"] = 0
                                    arquivo["total_packets"] = 0
                                    arquivo["last_packet"] = 0
                                paused = False
                                print()
                                print("========================================")
                                print("       TRANSMISSÃO REINICIADA")
                                print("========================================")

                            # ABORTAR
                            elif tecla == "a":
                                command_packet = build_packet(msg_type=ACK, control=ABORT)
                                send_packet(com1, command_packet)
                                transmission_aborted = True
                                transmission_finished = True
                                paused = False
                                print()
                                print("========================================")
                                print("       TRANSMISSÃO ABORTADA")
                                print("========================================")
                        time.sleep(0.05)
                
                elif control == RESTART:
                    for arquivo in received_files:
                        arquivo["data"] = b''
                        arquivo["received_packets"] = 0
                        arquivo["total_packets"] = 0
                        arquivo["last_packet"] = 0
                    print()
                    print("========================================")
                    print("       TRANSMISSÃO REINICIADA")
                    print("========================================")

                elif control == ABORT:
                    transmission_aborted = True
                    transmission_finished = True
                    print()
                    print("========================================")
                    print("       TRANSMISSÃO ABORTADA")
                    print("========================================")

            # FIM DE UM ARQUIVO
            elif msg_type == END_FILE:
                file_id = header["file_id"]
                file_info = received_files[file_id - 1]
                print()
                print("Arquivo completamente recebido:", file_info["name"])

            # FIM DE TODA A TRANSMISSÃO
            elif msg_type == END_TRANSFER:
                print()
                print("----------------------------------------")
                print("Fim da transmissão recebido.")
                print("----------------------------------------")
                transmission_finished = True
            # SE FOR OUTRA COISA
            else:
                print()
                print("Mensagem inesperada:", message_name(msg_type))

        # SALVA OS ARQUIVOS
        if transmission_aborted:
            print()
            print("Os arquivos incompletos não serão salvos.")
            com1.disable()
            return
        
        print()
        print("========================================")
        print("       SALVANDO ARQUIVOS")
        print("========================================")
        for file_info in received_files:
            path = os.path.join(pasta_cliente, file_info["name"])
            file = open(path, "wb")
            file.write(file_info["data"])
            file.close()
            print()
            print("Arquivo salvo:", path)

        # RESUMO FINAL
        print()
        print("========================================")
        print("       RESUMO DA TRANSMISSÃO")
        print("========================================")
        total_bytes = 0
        total_packets = 0
        for file_info in received_files:
            file_size = len(file_info["data"])
            packets_received = file_info["received_packets"]
            total_bytes += file_size
            total_packets += packets_received
            print()
            print("Arquivo:", file_info["name"])
            print("Tamanho recebido:", file_size, "bytes")
            print("Pacotes recebidos:", packets_received)
        print()
        print("----------------------------------------")
        print("Total de bytes recebidos:", total_bytes)
        print("Total de pacotes recebidos:", total_packets)
        print()
        print("========================================")
        print("       TRANSMISSÃO CONCLUÍDA")
        print("========================================")
        com1.disable()

    except Exception as erro:
        print()
        print("Ops! Ocorreu um erro no cliente.")
        print(erro)
        com1.disable()

if __name__ == "__main__":
    main()