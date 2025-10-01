# Parser de Sentenças NMEA - SETERA TELEMETRIA

Ferramenta simples para análise e interpretação de sentenças NMEA de sistemas de navegação GPS/GNSS.

## Descrição

Este software permite interpretar sentenças NMEA de qualquer sistema de satélites (GPS, GLONASS, Galileo, BeiDou, GNSS combinado) e exibir os dados de forma legível em português.

## Requisitos

- Python 3.x
- Biblioteca pynmea2

## Instalação

1. Instale as dependências:
```bash
pip install -r requirements.txt
```

ou

```bash
pip install pynmea2
```

## Como Usar

1. Execute o programa:
```bash
python parser_nmea.pyw
```

2. Cole uma sentença NMEA no campo de entrada

3. Clique no botão "PROCESSAR"

4. Veja os dados interpretados na área de resultado

## Tipos de Sentenças Suportadas

O parser suporta os seguintes tipos de sentenças NMEA:

- **GGA** - Dados de posicionamento GPS (latitude, longitude, altitude, qualidade, satélites)
- **RMC** - Informações mínimas de navegação (posição, velocidade, rumo, data/hora)
- **GSA** - DOP e satélites ativos (precisão, tipo de fix, satélites utilizados)
- **GSV** - Satélites visíveis (informações sobre cada satélite: elevação, azimute, SNR)
- **VTG** - Velocidade e rumo (velocidade em nós e km/h, rumo verdadeiro e magnético)
- **GLL** - Posição geográfica (latitude e longitude)
- **ZDA** - Data e hora UTC
- **GBS** - Detecção de falhas de satélite
- **HDT** - Rumo verdadeiro
- **VBW** - Velocidade água/solo
- E outras sentenças genéricas

## Sistemas de Satélites Suportados

O parser identifica automaticamente o sistema de satélites usado:

- **GP** - GPS
- **GL** - GLONASS
- **GA** - Galileo
- **GB** - BeiDou
- **GN** - GNSS (múltiplos sistemas combinados)
- **QZ** - QZSS
- E outros

## Exemplos de Sentenças

### GGA - Posicionamento GPS
```
$GNGGA,184353.07,1929.045,S,02410.506,E,1,04,2.6,100.00,M,-33.9,M,,0000*73
```

### RMC - Navegação
```
$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A
```

### GSA - DOP e Satélites Ativos
```
$GPGSA,A,3,04,05,,09,12,,,24,,,,,2.5,1.3,2.1*39
```

## Tratamento de Erros

O software trata graciosamente os seguintes erros:

- Sentenças com formato inválido
- Sentenças com checksum incorreto
- Sentenças de tipos não reconhecidos
- Dados incompletos ou corrompidos

## Características

- Interface gráfica simples e intuitiva
- Suporte a qualquer tipo de sentença NMEA
- Identificação automática do sistema de satélites
- Descrições em português para todos os campos
- Tratamento robusto de erros
- Área de saída com scroll para sentenças longas
- Formatação colorida para melhor legibilidade

## Arquivos

- `parser_nmea.pyw` - Programa principal
- `requirements.txt` - Dependências do Python
- `favicon.ico` - Ícone do aplicativo
- `test_parser.py` - Script de teste (opcional)
- `README.md` - Este arquivo

## Desenvolvido por

SETERA TELEMETRIA

---

Para suporte ou dúvidas sobre sentenças NMEA, consulte a documentação do protocolo NMEA 0183.
