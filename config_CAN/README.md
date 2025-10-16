# Atualização e Configuração - Leitor CANBUS v1.4

## Descrição

Software de atualização de firmware e configuração para leitores CANBUS da SETERA. Esta ferramenta permite atualizar o firmware de dispositivos CANBUS e configurar limites operacionais (RPM e velocidade) através de comunicação serial, fornecendo uma interface gráfica intuitiva com monitoramento em tempo real e workflow unificado.

**Versão:** 1.4
**Data de Lançamento:** 16Out2025
**Parte do:** SETERA Dashboard Tools Suite

## Características

- **Interface Gráfica Intuitiva**: Desenvolvida em Python Tkinter com todos os textos em Português Brasileiro
- **Suporte Universal V2 e V3+**: Detecção automática e protocolo otimizado para dispositivos V2 (firmware 2.x) e V3+ (firmware 3.x)
- **Detecção Automática de Portas COM**: Atualização automática a cada 1 segundo das portas seriais disponíveis
- **Comunicação Serial Configurada**: Taxa de transmissão fixa de 115200 baud
- **Workflow Unificado de Atualização e Configuração**:
  - Processo integrado: firmware + configuração em uma única operação
  - Seleção de arquivo .frm na pasta Downloads
  - Configuração de limites pré-preenchida (90 km/h, 2400 RPM)
  - Aplicação automática da configuração após atualização de firmware
  - Barra de progresso com percentual preciso
  - Mecanismo de retry automático (5 tentativas para UPDATE, 3 para LIMITS)
  - Notificações de sucesso/falha detalhadas
- **Configuração de Limites**:
  - Velocidade máxima (10-200 km/h) - padrão 90 km/h
  - Limite de RPM (100-10000, múltiplos de 64) - padrão 2400 RPM
  - Diálogo de configuração intuitivo com valores pré-preenchidos
  - Validação de entrada em tempo real
  - Aplicação automática após firmware update
- **Detecção Inteligente de Dispositivo**:
  - Ativação automática de dispositivos dormentes
  - Detecção de modo sleep (sem FR1 por 2+ segundos)
  - Habilitação/desabilitação automática de botões
  - Feedback visual com cores (verde=ativo, vermelho=inativo)
- **Sistema de Log Otimizado**:
  - Timestamps com precisão de milissegundos
  - Codificação por cores (branco=TX, amarelo=RX, verde limão=sucesso, laranja=erro)
  - Supressão inteligente de frames FR1 e dados de firmware durante update
  - Progresso mostrado a cada 1000 frames
  - Log limpo e legível
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
   - Botão **INICIAR UPDATE** fica verde (habilitado)
   - Monitoramento FR1 inicia automaticamente

### 4. Atualização de Firmware e Configuração (Processo Unificado)

#### Passo 1: Iniciar Processo
1. Com o dispositivo conectado, clique no botão **INICIAR UPDATE**
2. O file picker abrirá automaticamente na pasta **Downloads**
3. Selecione o arquivo .frm desejado e clique em "Abrir"
4. O software analisa o arquivo e exibe informações no log:
   - Número serial do dispositivo
   - Versão do firmware
   - Número total de frames
   - Checksum

#### Passo 2: Configurar Limites
1. Após selecionar o firmware, o diálogo de configuração abre automaticamente
2. Os campos vêm pré-preenchidos com:
   - **Velocidade Máxima**: 90 km/h
   - **Limite RPM**: 2400 RPM
3. Ajuste os valores conforme necessário:
   - **Velocidade Máxima**: 10-200 km/h
   - **Limite RPM**: 100-10000 (será arredondado para múltiplo de 64)
4. Clique em **OK** para continuar ou **CANCELAR** para abortar

#### Passo 3: Confirmar Atualização
1. Um diálogo de confirmação mostra:
   - Versão do firmware a ser instalado
   - Número de frames
   - Configuração de limites que será aplicada
2. Clique em **SIM** para confirmar ou **NÃO** para cancelar

#### Passo 4: Acompanhar Progresso
1. A atualização inicia automaticamente:
   - Comando @FRM,START enviado
   - Frames de firmware enviados (progresso a cada 1000 frames)
   - Comando @FRM,UPGRADE enviado
   - Aguarda 1 segundo
   - Comando LIMITS enviado automaticamente
2. Acompanhe através da:
   - Barra de progresso verde
   - Percentual exibido ao lado da barra
   - Log detalhado (sem poluição de frames FR1 ou dados de firmware)
3. **NÃO** desconecte o dispositivo durante o processo

#### Passo 5: Conclusão
- Se bem-sucedido: Popup "Atualização de firmware e configuração concluídas com sucesso!"
- Se houver erro no firmware: Mensagem de erro específica (ex: ERR#82 para firmware incompatível)
- Se configuração falhar: Firmware é atualizado, mas aparece aviso sobre falha na configuração
- Após conclusão: Desconecte clicando em **DESCONECTAR** se necessário

### 5. Detecção Automática de Sleep

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

## Protocolo de Atualização e Configuração

O software implementa o protocolo descrito nas seções 7.1-7.3 do documento `canbus_reader_protocol.pdf`, com adição de configuração automática:

1. **Inicialização**: Envio do comando `@FRM,START`
2. **Transferência de Frames**: Envio sequencial de todos os frames com confirmação `OK` após cada frame
3. **Aplicação do Firmware**: Envio do comando `@FRM,UPGRADE` para aplicar o firmware
4. **Aguardo**: Pausa de 1 segundo após confirmação do UPGRADE
5. **Configuração Automática**: Envio do comando `LIMITS,<speed>,0,<rpm>` com retry (3 tentativas)

### Formato de Comunicação
- **Header**: (vazio)
- **Footer**: `\r\n` (CR+LF)
- **Respostas Esperadas**:
  - Sucesso: `OK` ou `LIMITS:OK`
  - Erro: `ERR#<código>`
  - ERR#82: Firmware não corresponde ao número de série do dispositivo

## Sistema de Log

### Cores
- **Branco**: Dados enviados ao dispositivo (TX)
- **Amarelo**: Dados recebidos do dispositivo (RX)
- **Verde Limão**: Mensagens de sucesso (melhor contraste)
- **Laranja**: Mensagens de erro (melhor contraste)
- **Ciano**: Informações gerais

### Supressão Inteligente
- **Frames FR1**: Não aparecem no log (mas são monitorados internamente)
- **Dados de Firmware**: Durante update, apenas comandos START/UPGRADE e progresso a cada 1000 frames são exibidos
- **Resultado**: Log limpo, legível e focado em informações relevantes

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

### v1.4 - 16Out2025
- **Suporte Completo para Dispositivos V2**: Detecção automática e protocolo otimizado para leitores V2 (firmware 2.x)
- **Detecção Automática de Versão**: Identifica automaticamente dispositivos V2 vs V3+ baseado na resposta VERSIONS
- **Protocolo V2 Aprimorado**:
  - Atraso de 500ms após comando START para dispositivos V2 (preparação de memória)
  - Tratamento correto de respostas `@FRM:OK` (com dois pontos) para V2
  - Modo debug que loga os primeiros 5 frames para diagnóstico V2
- **Melhor Diagnóstico**: Log detalhado de erros com resposta exata recebida do dispositivo
- **Compatibilidade**: Mantém total compatibilidade com dispositivos V3+ (firmware 3.x)

### v1.3 - 15Out2025
- **Workflow Unificado**: Firmware update e configuração em um único processo
- **Remoção do Botão CONFIGURAR**: Configuração agora é integrada ao processo de update
- **Configuração Automática**: Valores pré-preenchidos (90 km/h, 2400 RPM)
- **File Picker Otimizado**: Abre automaticamente na pasta Downloads
- **Log Otimizado**:
  - Supressão de frames FR1 (reduz poluição visual)
  - Supressão de dados de firmware durante update
  - Progresso mostrado a cada 1000 frames (ao invés de 250)
  - Cores melhoradas: Verde limão (sucesso) e Laranja (erro) para melhor contraste
- **Detecção de Erro ERR#82**: Mensagem específica para firmware incompatível com SN do dispositivo
- **Processo Sequencial**: Após firmware update bem-sucedido, aguarda 1s e envia configuração LIMITS automaticamente

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
