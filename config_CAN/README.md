# Atualização e Configuração - Leitor CANBUS v1.0

## Descrição

Software de atualização de firmware e configuração para leitores CANBUS da SETERA. Esta ferramenta permite atualizar o firmware de dispositivos CANBUS e configurar limites operacionais (RPM e velocidade) através de comunicação serial, fornecendo uma interface gráfica intuitiva com monitoramento em tempo real.

**Versão:** 1.0
**Data de Lançamento:** 14Out2025
**Parte do:** SETERA Dashboard Tools Suite

## Características

- **Interface Gráfica Intuitiva**: Desenvolvida em Python Tkinter com todos os textos em Português Brasileiro
- **Detecção Automática de Portas COM**: Atualização automática a cada 1 segundo das portas seriais disponíveis
- **Comunicação Serial Configurada**: Taxa de transmissão fixa de 115200 baud
- **Atualização de Firmware**:
  - Seleção manual de arquivos .frm
  - Barra de progresso com percentual preciso
  - Mecanismo de retry automático (5 tentativas)
  - Notificações de sucesso/falha
- **Configuração de Limites**:
  - Velocidade máxima (10-200 km/h)
  - Limite de RPM (100-10000, múltiplos de 64)
  - Diálogo de configuração intuitivo
  - Validação de entrada em tempo real
- **Detecção Inteligente de Dispositivo**:
  - Ativação automática de dispositivos dormentes
  - Detecção de modo sleep (sem FR1 por 2+ segundos)
  - Habilitação/desabilitação automática de botões
  - Feedback visual com cores (verde=ativo, vermelho=inativo)
- **Sistema de Log Detalhado**:
  - Timestamps com precisão de milissegundos
  - Codificação por cores (branco=TX, amarelo=RX, verde=sucesso, vermelho=erro)
  - Registro completo de toda a comunicação
- **Mecanismo de Retry Inteligente**:
  - 3 tentativas para comandos VERSIONS e LIMITS
  - 5 tentativas para início de atualização de firmware
  - Detecção imediata de FR1 para reenvio de comandos

## Requisitos do Sistema

### Python
- Python 3.7 ou superior

### Bibliotecas Necessárias
```bash
pip install pyserial
```

### Bibliotecas Padrão (já incluídas no Python)
- tkinter
- threading
- datetime
- pathlib

## Estrutura de Arquivos

```
config_CAN/
├── config_can.pyw          # Aplicação principal
├── favicon.ico             # Ícone da janela
├── README.md               # Este arquivo
├── canbus_reader_protocol.pdf  # Documentação do protocolo
└── CL_v3.0.18b_sn3035331_asc.frm  # Exemplo de arquivo de firmware
```

## Como Usar

### 1. Instalação
1. Certifique-se de ter o Python 3.7+ instalado
2. Instale a biblioteca pyserial:
   ```bash
   pip install pyserial
   ```

### 2. Execução
Execute o arquivo principal:
```bash
python config_can.pyw
```
ou simplesmente clique duas vezes no arquivo `config_can.pyw`

### 3. Conectar ao Dispositivo

1. Conecte o leitor CANBUS ao computador via cabo USB/Serial
2. Aguarde até que a porta COM apareça no dropdown (atualização automática a cada 1s)
3. Selecione a porta COM correta no dropdown
4. Clique no botão **CONECTAR**
5. O software envia comando VERSIONS automaticamente (3 tentativas com retry inteligente)
6. Após conexão bem-sucedida:
   - Informações do dispositivo aparecem na interface (FW, SN)
   - Botões **INICIAR UPDATE** e **CONFIGURAR** ficam verdes (habilitados)
   - Monitoramento FR1 inicia automaticamente

### 4. Atualização de Firmware

#### Passo 1: Selecionar Firmware
1. Clique no botão **SELECIONAR FIRMWARE**
2. Navegue até o arquivo .frm desejado
3. Selecione o arquivo e clique em "Abrir"
4. O software irá analisar o arquivo e exibir informações no log:
   - Número serial do dispositivo
   - Versão do firmware
   - Número total de frames
   - Checksum

#### Passo 2: Iniciar Atualização
1. Após selecionar o firmware, clique no botão **INICIAR UPDATE**
2. Acompanhe o progresso através da:
   - Barra de progresso verde
   - Percentual exibido ao lado da barra
   - Log detalhado de comunicação
3. **NÃO** desconecte o dispositivo durante a atualização

#### Passo 3: Conclusão
- Se bem-sucedido: Popup "Atualização concluída com sucesso!"
- Se houver erro: Mensagem de erro com detalhes
- Após conclusão: Desconecte clicando em **DESCONECTAR** se necessário

### 5. Configuração de Limites

#### Passo 1: Abrir Diálogo de Configuração
1. Com o dispositivo conectado e botões habilitados (verdes)
2. Clique no botão **CONFIGURAR**
3. Diálogo de configuração será aberto

#### Passo 2: Inserir Valores
1. **Velocidade Máxima**: Digite um valor entre 10 e 200 km/h
2. **Limite RPM**: Digite um valor entre 100 e 10000
   - O software automaticamente arredonda para o múltiplo de 64 mais próximo
3. Clique em **OK** para aplicar ou **Cancelar** para descartar

#### Passo 3: Confirmação
- Comando LIMITS é enviado com retry automático (3 tentativas)
- Mensagem de sucesso/erro aparece no log
- Configurações são aplicadas imediatamente no dispositivo

### 6. Detecção Automática de Sleep

O software monitora automaticamente a atividade do dispositivo:

- **Dispositivo Ativo**: Envia frames FR1 a cada ~1 segundo
  - Botões permanecem **verdes** (habilitados)
- **Dispositivo Dorme**: Sem FR1 por mais de 2 segundos
  - Botões ficam **vermelhos** (desabilitados)
  - Log mostra: "Dispositivo entrou em modo dormante, botões desabilitados"
- **Dispositivo Acorda**: FR1 retorna
  - Botões voltam a ficar **verdes** (habilitados)
  - Log mostra: "Dispositivo reativado, botões habilitados"

## Formato do Arquivo de Firmware (.frm)

Os arquivos de firmware seguem um formato de texto específico:

```
# Comentários começam com '#'
D<NÚMERO_SERIAL>        # Ex: D3035331
V<VERSÃO>               # Ex: V3.0.18b
N<NÚMERO_DE_FRAMES>     # Ex: N3826
C<CHECKSUM>             # Ex: C0x12AB
@FRM,<74_DÍGITOS_HEX>   # Frames de dados do firmware
```

### Exemplo:
```
#CANBUS Leitor - Firmware v3.0.18b
D3035331
V3.0.18b
N3826
C0x4A2F
@FRM,000000000000000000000000000000000000000000000000000000000000000000000000
@FRM,111111111111111111111111111111111111111111111111111111111111111111111111
...
```

## Protocolo de Atualização

O software implementa o protocolo descrito nas seções 7.1-7.3 do documento `canbus_reader_protocol.pdf`:

1. **Inicialização**: Envio do comando `@FRM,START`
2. **Transferência de Frames**: Envio sequencial de todos os frames com confirmação `OK` após cada frame
3. **Finalização**: Envio do comando `@FRM,UPGRADE` para aplicar o firmware

### Formato de Comunicação
- **Header**: (vazio)
- **Footer**: `\r\n` (CR+LF)
- **Respostas Esperadas**:
  - Sucesso: `OK`
  - Erro: `ERR#<código>`

## Sistema de Log

### Cores
- **Branco**: Dados enviados ao dispositivo (TX)
- **Amarelo**: Dados recebidos do dispositivo (RX)
- **Verde**: Mensagens de sucesso
- **Vermelho**: Mensagens de erro
- **Ciano**: Informações gerais

### Formato de Timestamp
Todos os logs incluem timestamp no formato: `[HH:MM:SS.mmm]`
- HH: Horas (00-23)
- MM: Minutos (00-59)
- SS: Segundos (00-59)
- mmm: Milissegundos (000-999)

## Solução de Problemas

### Porta COM não aparece
- Verifique se o cabo USB está conectado corretamente
- Verifique se os drivers do dispositivo estão instalados
- Tente reconectar o dispositivo
- Aguarde até 1 segundo para a atualização automática

### Erro ao conectar
- Verifique se nenhum outro software está usando a porta COM
- Certifique-se de que a porta selecionada está correta
- Tente desconectar e reconectar o dispositivo

### Atualização falha no meio do processo
- Não interrompa a atualização em andamento
- Se falhar, anote o erro exibido no log
- Tente desconectar e reconectar o dispositivo
- Execute a atualização novamente do início

### Arquivo de firmware inválido
- Verifique se o arquivo .frm não está corrompido
- Certifique-se de que o arquivo contém as linhas D, V, N, C
- Verifique se os frames começam com `@FRM,`

## Notas Técnicas

- **Baud Rate**: 115200 (fixo, não configurável)
- **Timeout Serial**: 1 segundo
- **Intervalo de Refresh de Portas**: 1 segundo
- **Thread de Comunicação**: Execução em thread separada para não bloquear a interface

## Suporte

Para questões técnicas ou problemas com o software, entre em contato com o suporte técnico da SETERA.

## Changelog

### v1.0 - 14Out2025
- Lançamento inicial
- Interface gráfica completa em Português Brasileiro
- Implementação do protocolo de atualização de firmware
- Sistema de log com timestamps e cores
- Detecção automática de portas COM
- Barra de progresso com percentual preciso

---

**SETERA Dashboard Tools Suite**
© 2025 SETERA. Todos os direitos reservados.
