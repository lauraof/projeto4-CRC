import time

HEADER_SIZE = 10
MAX_PAYLOAD_SIZE = 100

EOP = b'\xAA\xBB\xCC\xDD'

# TIPOS DE MENSAGEM
HANDSHAKE = 1
# Servidor envia a lista de arquivos disponíveis.
FILE_LIST = 2
# Cliente solicita um arquivo.
FILE_REQUEST = 3
# Servidor confirma o arquivo escolhido.
FILE_SELECTED = 4
# Cliente informa que terminou de escolher arquivos.
FINISH_SELECTION = 5
# Servidor avisa que vai começar a transmissão.
START_TRANSFER = 6
# Pacote contendo dados de um arquivo.
DATA = 7
# Confirmação de recebimento de um pacote.
ACK = 8
# Indica que um arquivo terminou.
END_FILE = 9
# Indica que todos os arquivos terminaram.
END_TRANSFER = 10
# Indica que houve erro na verificação do CRC
CRC_ERROR = 11

# COMANDOS DE CONTROLE
NORMAL = 0
PAUSE = 1
CONTINUE = 2
RESTART = 3
ABORT = 4


# ============================================================
# HEADER
# ============================================================
#
# Cada posição possui exatamente 1 byte.
#
# H0 -> tipo da mensagem
# H1 -> ID do arquivo
# H2 -> número do pacote
# H3 -> quantidade total de pacotes
# H4 -> tamanho do payload
# H5 -> número do pacote confirmado (ACK)
# H6 -> campo auxiliar / controle
# H7 -> reservado
# H8 -> crc 1/2
# H9 -> crc 2/2
#
# ============================================================


def build_header(msg_type=0, file_id=0, packet_number=0, total_packets=0, payload_size=0, ack_number=0, control=0, h7=0, crc1=b'\x00', crc2=b'\x00'):
    fields = [msg_type, file_id, packet_number, total_packets, payload_size, ack_number, control, h7]
    return bytes(fields) + crc1 + crc2


def parse_header(header):
    return {
        "msg_type": header[0],
        "file_id": header[1],
        "packet_number": header[2],
        "total_packets": header[3],
        "payload_size": header[4],
        "ack_number": header[5],
        "control": header[6],
        "h7": header[7],
        "crc1": header[8],
        "crc2": header[9],
    }


# ============================================================
# DATAGRAMA
# ============================================================


def build_packet(msg_type, payload=b'', file_id=0, packet_number=0, total_packets=0, ack_number=0, control=0, crc1=b'\x00', crc2=b'\x00'):
    header = build_header(
        msg_type=msg_type,
        file_id=file_id,
        packet_number=packet_number,
        total_packets=total_packets,
        payload_size=len(payload),
        ack_number=ack_number,
        control=control,
        crc1=crc1,
        crc2=crc2)

    return header + payload + EOP


def parse_packet(packet):
    header = packet[:HEADER_SIZE]
    header_info = parse_header(header)
    payload_size = header_info["payload_size"]
    payload_start = HEADER_SIZE
    payload_end = HEADER_SIZE + payload_size
    payload = packet[payload_start:payload_end]
    return header_info, payload


# ============================================================
# FRAGMENTAÇÃO DE ARQUIVOS
# ============================================================


def fragment_data(data, chunk_size=MAX_PAYLOAD_SIZE):
    return [
        data[i:i+chunk_size]
        for i in range(0, len(data), chunk_size)]


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================


def message_name(msg_type):
    names = {
        HANDSHAKE: "HANDSHAKE",
        FILE_LIST: "FILE_LIST",
        FILE_REQUEST: "FILE_REQUEST",
        FILE_SELECTED: "FILE_SELECTED",
        FINISH_SELECTION: "FINISH_SELECTION",
        START_TRANSFER: "START_TRANSFER",
        DATA: "DATA",
        ACK: "ACK",
        END_FILE: "END_FILE",
        END_TRANSFER: "END_TRANSFER",
        CRC_ERROR: "CRC_ERROR",}
    return names.get(msg_type, f"UNKNOWN({msg_type})")

def send_packet(com1, packet):
    com1.sendData(packet)
    while com1.tx.getIsBussy():
        time.sleep(0.05)

def escreve_arquivo_c(env_rec, tipo_msg, tamanho=14, arquivo=0, pacote=0, total_pacote=0, crc_pacote=0):
    data_hora = time.strftime("%d/%m/%Y %H:%M:%S")
    if tamanho == 14 or tipo_msg.startswith("FILE"):
        linha = f'{data_hora} | {env_rec} | tipo_mensagem: {tipo_msg} | tamanho_pacote: {tamanho}'
    else:
        linha = f'{data_hora} | {env_rec} | tipo_mensagem: {tipo_msg} | tamanho_pacote: {tamanho} | arquivo: {arquivo} | num_pacote: {pacote} | total_pacotes: {total_pacote} | crc: {crc_pacote}'
    with open("log-client.txt", "a") as log:
        log.write(linha+"\n")

def escreve_arquivo_s(env_rec, tipo_msg, tamanho=14, arquivo=0, pacote=0, total_pacote=0, crc_pacote=0):
    data_hora = time.strftime("%d/%m/%Y %H:%M:%S")
    if tamanho == 14 or tipo_msg.startswith("FILE"):
        linha = f'{data_hora} | {env_rec} | tipo_mensagem: {tipo_msg} | tamanho_pacote: {tamanho}'
    else:
        linha = f'{data_hora} | {env_rec} | tipo_mensagem: {tipo_msg} | tamanho_pacote: {tamanho} | arquivo: {arquivo} | num_pacote: {pacote} | total_pacotes: {total_pacote} | crc: {crc_pacote}'
    with open("log-server.txt", "a") as log:
        log.write(linha+"\n")