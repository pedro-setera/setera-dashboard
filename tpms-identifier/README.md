# Identificador de Sensores TPMS - SETERA TELEMETRIA

Ferramenta para identificação e análise de sensores TPMS (Tire Pressure Monitoring System) via comunicação serial.

## Descrição

Este software permite receber, interpretar e exibir dados de sensores TPMS enviados por um receptor TPMS conectado via porta serial. O sistema decodifica automaticamente os dados hexadecimais e apresenta as informações em português de forma clara e organizada.

## Requisitos

- Python 3.x
- Biblioteca pyserial

## Instalação

1. Instale as dependências:
```bash
pip install -r requirements.txt
```

ou

```bash
pip install pyserial
```

## Como Usar

1. Execute o programa:
```bash
python tpms_identifier.pyw
```

2. Selecione a porta COM do receptor TPMS

3. Clique em "CONECTAR" para iniciar a comunicação (9600 baud)

4. Force o sensor TPMS a transmitir suas informações

5. Veja os dados interpretados na interface

## Protocolo TPMS

### Estrutura da Mensagem

As mensagens TPMS são enviadas em formato ASCII hexadecimal com a seguinte estrutura:

```
TPV | Flag | ID1 | ID2 | ID3 | Temp | Pressure | Battery | Checksum+CR/LF
```

**Exemplo:**
```
54 50 56 2C A7 00 2C 00 0F 2C 00 65 2C 00 FA 2C 00 8E 2C 00 63 2C 00 FF 2C 00 D6 0D 0A
```

### Campos da Mensagem

1. **Header (TPV):** Sempre `54 50 56` (bytes ASCII de "TPV")

2. **Flag de Função:**
   - `A7` = Dados normais (sem alarmes)
   - `02` = Alarme de vazamento de ar
   - `01` = Alarme de bateria fraca

3. **Número do Sensor:** Identificador sequencial do pneu

4. **ID do Sensor (3 bytes):** ID1 + ID2 + ID3 formam o código único do sensor

5. **Temperatura:**
   - Fórmula: `(valor_hex - 50)` = °Celsius
   - Exceção: `0x57` deve ser ignorado (código de aprendizado)
   - Em frames de vazamento: valor fixo `0x57`

6. **Pressão:**
   - Fórmula PSI: `valor_hex × 0.74` = PSI
   - Fórmula kPa: `valor_hex × 1.37` = kPa
   - Em frames de vazamento: `0x00`

7. **Status da Bateria:**
   - `0xFF` = Bateria OK
   - `0x00` = Bateria fraca

8. **Checksum:** Verificação de integridade dos dados

### Cálculo do Checksum

O checksum varia de acordo com o flag:

- **Flag 0xA7 (Normal):**
  `Checksum = ID1 + ID2 + ID3 + Pressure + Temp + 0x77`

- **Flag 0x02 (Vazamento):**
  `Checksum = (0x80 | ID1) + ID2 + ID3 + Pressure + Temp + 0x77`

- **Flag 0x01 (Bateria Fraca):**
  `Checksum = (0x40 | ID1) + ID2 + ID3 + Pressure + Temp + 0x77`

*Nota: Usar apenas o último byte do resultado*

## Tipos de Frames

### Frame Normal
Contém todos os dados do sensor: ID, pressão, temperatura e status da bateria.

### Frame de Vazamento
- Flag: `0x02`
- Temperatura: Ignorada (valor fixo `0x57` - código de aprendizado)
- Pressão: Ignorada (valor `0x00`)
- Foco: Alarme de vazamento de ar

### Frame de Bateria Fraca
- Flag: `0x01`
- Indica que a bateria do sensor está baixa
- Contém todos os outros dados normalmente

## Interface do Software

### Seção de Conexão
- Seleção de porta COM
- Botão CONECTAR/DESCONECTAR
- Botão LIMPAR LOG

### Log de Dados
- Exibe os dados hexadecimais brutos recebidos
- Mostra resumo da interpretação para cada frame
- Fundo preto com texto verde (estilo terminal)
- **Auto-clear:** Limpa automaticamente quando nova string chega

### Dados Interpretados
Exibe os campos decodificados:
- **ID do Sensor:** Código único em formato uppercase sem espaços (ex: 000F009200BC)
  - Botão **COPIAR ID** para copiar o ID diretamente para a área de transferência
  - Feedback visual quando copiado (botão muda para "COPIADO!")
- **Status:** Normal, Vazamento ou Bateria Fraca
- **Pressão:** Em PSI e kPa
- **Temperatura:** Em graus Celsius
- **Bateria:** OK ou FRACA
- **Checksum:** Validação (✓ Válido / ✗ Inválido)

## Exemplos de Uso

### Sensor Normal (105 PSI / 49°C)
```
Entrada: 54 50 56 2C A7 00 2C 00 0F 2C 00 65 2C 00 FA 2C 00 8E 2C 00 63 2C 00 FF 2C 00 D6 0D 0A

Resultado:
  ID: 000F006500FA
  Status: Normal (sem alarmes)
  Pressão: 73.3 PSI (135.6 kPa)
  Temperatura: 92°C
  Bateria: OK
  Checksum: ✓ Válido
```

### Alarme de Vazamento (20 PSI)
```
Entrada: 54 50 56 2C 02 00 2C 00 0F 2C 00 65 2C 00 FA 2C 00 1B 2C 00 57 2C 00 FF 2C 00 D7 0D 0A

Resultado:
  ID: 000F006500FA
  Status: VAZAMENTO DE AR
  Pressão: N/A (frame de vazamento)
  Temperatura: N/A (frame de vazamento)
  Bateria: OK
  Checksum: ✓ Válido
```

### Alarme de Bateria Fraca (110 PSI / 49°C)
```
Entrada: 54 50 56 2C 01 00 2C 00 0F 2C 00 65 2C 00 FA 2C 00 95 2C 00 63 2C 00 00 2C 00 1D 0D 0A

Resultado:
  ID: 000F006500FA
  Status: BATERIA FRACA
  Pressão: 73.3 PSI (135.6 kPa)
  Temperatura: 99°C
  Bateria: FRACA
  Checksum: ✓ Válido
```

## Arquivos

- `tpms_identifier.pyw` - Programa principal
- `requirements.txt` - Dependências Python
- `favicon.ico` - Ícone da aplicação
- `test_tpms_parser.py` - Script de teste do parser
- `TPMS_Protocol_20200122.docx` - Documentação do protocolo
- `TPMS data filtering rules_21082802.docx` - Regras de filtragem
- `TPMS filtering test frames.txt` - Frames de teste
- `README.md` - Este arquivo

## Desenvolvido por

SETERA TELEMETRIA

---

Para mais informações sobre o protocolo TPMS, consulte os documentos de referência incluídos na pasta do projeto.
