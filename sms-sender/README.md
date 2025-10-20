# Sistema Automatizado de Envio de Comandos SMS

**Versão:** 2.3
**Data:** 20 de Outubro de 2025
**Plataforma:** Windows/Linux/macOS
**Linguagem:** Python 3.8+

---

## 📱 Visão Geral

O **Sistema Automatizado de Envio de Comandos SMS** é uma ferramenta de automação desenvolvida para enviar comandos de configuração via SMS para múltiplos dispositivos GPS de câmeras veiculares de forma sequencial e automatizada. A aplicação utiliza uma interface gráfica moderna construída com ttkbootstrap e se comunica com um módulo GSM SIM800C através de um Arduino Uno R4 que atua como ponte serial.

### Características Principais

- ✅ Interface gráfica moderna e intuitiva (tema escuro)
- ✅ **Integração com API SETERA** - Busca automática de terminais STR-CAM
- ✅ **Multi-seleção de terminais** - Selecione múltiplos equipamentos de uma vez
- ✅ **Command Queue Builder** - Adicione múltiplos comandos por terminal
- ✅ **Terminal × Command Multiplication** - 3 terminais × 2 comandos = 6 entradas automáticas
- ✅ Envio automatizado de SMS para múltiplos dispositivos
- ✅ **Sistema inteligente de validação de respostas** (pattern matching)
- ✅ **Comandos individuais por dispositivo** (configuráveis via JSON)
- ✅ **Detecção automática de tipo de comando** (FTP, APN, etc.)
- ✅ Gerenciamento completo de lista de comandos (adicionar, editar, remover, remover todos)
- ✅ **Multi-select deletion** - Remova múltiplos comandos com Ctrl+Click
- ✅ Importação em lote de equipamentos via arquivo de texto
- ✅ Monitoramento de status em tempo real com código de cores
- ✅ Sistema de logs detalhado com código de cores
- ✅ Controles de pausa e retomada durante a automação
- ✅ Barra de progresso visual
- ✅ Teste de conectividade com módulo GSM
- ✅ Exportação de logs para análise posterior
- ✅ Configurações persistentes (salvas automaticamente)

---

## 🏗️ Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                    Aplicação Python GUI                          │
│              (sms_automation_gui.pyw)                            │
│                                                                  │
│  • Interface gráfica (ttkbootstrap)                             │
│  • Integração com API SETERA (OAuth2)                           │
│  • Lógica de automação e gerenciamento de estado               │
│  • Processamento de comandos AT                                 │
│  • Sistema de filas para comunicação entre threads             │
│  • Logging e persistência de configurações                      │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ USB Serial (9600 baud)
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Arduino Uno R4                                │
│                 (serial_bridge.ino)                              │
│                                                                  │
│  • Ponte serial transparente (passthrough)                      │
│  • Sem processamento ou lógica de negócios                      │
│  • Encaminhamento bidirecional byte-a-byte                      │
│  • Usa Hardware Serial1 (UART dedicado)                         │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ Hardware Serial1
                              │ Pinos 0 (RX) e 1 (TX)
                              │ 9600 baud
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Módulo GSM SIM800C                            │
│                 (Shield para Arduino)                            │
│                                                                  │
│  • Modem GSM para transmissão/recepção de SMS                   │
│  • Processa comandos AT padrão                                  │
│  • Requer chip SIM ativo com créditos                           │
└──────────────────────────────────────────────────────────────────┘
```

### Componentes do Sistema

1. **Aplicação Python (GUI)**
   - Gerencia interface com o usuário
   - Integra com API SETERA para buscar terminais STR-CAM
   - Controla lógica de automação
   - Processa protocolo AT de comandos SMS
   - Gerencia threads de trabalho e filas de mensagens

2. **Arduino Uno R4 (Ponte Serial)**
   - Firmware simples de encaminhamento serial
   - Não processa ou interpreta comandos
   - Conecta USB (PC) ao SIM800C via Hardware Serial1 (UART dedicado)
   - Usa pinos 0 (RX) e 1 (TX) para comunicação com SIM800C

3. **Módulo SIM800C (Hardware GSM)**
   - Modem GSM/GPRS para transmissão SMS
   - Requer chip SIM com operadora ativa
   - Antena GSM para recepção de sinal

---

## 🚀 Instalação e Configuração

### Requisitos de Hardware

1. **Computador** com porta USB disponível
2. **Arduino Uno R4** (ou compatível)
3. **Shield SIM800C** para Arduino
4. **Chip SIM** ativo com plano de dados/SMS
5. **Cabo USB** (tipo A para tipo B)
6. **Fonte de alimentação** adequada (2A+ para transmissão GSM)
7. **Antena GSM** conectada ao módulo SIM800C

### Requisitos de Software

#### Python 3.8 ou superior

Verifique se o Python está instalado:
```bash
python --version
```

#### Dependências Python

Instale as bibliotecas necessárias:
```bash
pip install ttkbootstrap pyserial requests
```

**Bibliotecas utilizadas:**
- `ttkbootstrap` - Framework de interface gráfica moderna
- `pyserial` - Comunicação serial com Arduino
- `requests` - Comunicação com API SETERA

### Configuração do Hardware

#### Passo 1: Montar o Hardware

**⚠️ CONFIGURAÇÃO CRÍTICA - Shield Keyestudio SIM800C (Ks0254):**

1. Conecte o **Shield SIM800C** ao **Arduino Uno R4**

2. **🔴 JUMPER CAPS (MUITO IMPORTANTE!):**
   - Localize os jumper caps/pinos de seleção no shield
   - **CONECTE OS JUMPERS EM D0/D1** (Hardware Serial1)
   - ❌ **NÃO conecte em D6/D7** (SoftwareSerial não funciona no R4!)

3. **DIP Switch de Alimentação:**
   - **EXTERN:** Use fonte externa 7-12V, 2A+ (recomendado)
   - **ARDUINO:** Alimenta através do Arduino (requer fonte adequada)

4. **Verifique as conexões (via jumpers):**
   - SIM800C TX → Arduino Pino 0 (RX - Hardware Serial1)
   - SIM800C RX → Arduino Pino 1 (TX - Hardware Serial1)
   - Pino 9 → Controle automático de power (via firmware)

5. Insira o **chip SIM ativo** no slot do SIM800C

6. Conecte a **antena GSM** ao conector apropriado

7. Conecte a **fonte de alimentação** (7-12V DC, mínimo 2A)

#### Passo 2: Carregar Firmware no Arduino

1. Abra o **Arduino IDE**
2. Abra o arquivo **`serial_bridge.ino`**
3. Selecione a placa: **Ferramentas → Placa → Arduino Uno R4 WiFi**
4. Selecione a porta: **Ferramentas → Porta → COM_X** (Windows) ou **/dev/ttyUSBX** (Linux)
5. Clique em **Upload** (→)
6. Aguarde a mensagem: "Upload concluído"

**Características do firmware:**
- ✅ Usa Hardware Serial1 nos pinos 0 (RX) e 1 (TX)
- ✅ Baudrate fixo: 9600 para comunicação com SIM800C
- ✅ Power-on automático via pino 9
- ✅ Delay de boot de 3 segundos (aguarda shield inicializar)
- ✅ Mensagens de debug no Serial Monitor

#### Passo 3: Verificar Funcionamento

1. Abra o **Monitor Serial** no Arduino IDE (9600 baud)
2. Você deve ver:
   ```
   SMS Serial Bridge Ready
   USB Serial: 9600 baud
   SIM800C Hardware Serial1: 9600 baud
   ```

3. **Aguarde 3 segundos** (tempo de boot do shield)
4. Digite: `AT` e pressione Enter
5. Resposta esperada: `OK`

**Se não houver resposta, verifique:**
- ❌ **Jumper caps** estão em D0/D1? (NÃO em D6/D7!)
- ❌ Chip SIM inserido corretamente?
- ❌ Antena GSM conectada?
- ❌ Alimentação adequada (7-12V, 2A+)?
- ❌ DIP switch na posição correta?
- ❌ Botão "To Start" pressionado por 2-3 segundos no shield?

### Configuração da Aplicação Python

#### Executar a Aplicação

```bash
# A partir do diretório sms-sender
python sms_automation_gui.pyw
```

Ou no Windows, basta dar duplo clique em `sms_automation_gui.pyw`.

#### Primeira Execução

1. A aplicação criará automaticamente o arquivo `sms_config.json`
2. A **porta COM** é detectada automaticamente (lista atualiza a cada segundo)
3. **Baudrate é fixo em 9600** (hardcoded para máxima confiabilidade)
4. Clique em **🔌 Conectar** para estabelecer comunicação
5. A aplicação autentica automaticamente com a API SETERA em background
6. Use **⚡ Testar Módulo** para verificar conectividade GSM

---

## 📖 Guia de Uso

### Interface Principal

A aplicação é dividida em seções:

#### Área de Status (Superior Direita)

Exibe informações em tempo real da conexão:
- **● Status da Conexão**: Desconectado (vermelho) / Conectado (verde) / Validação Falhou (vermelho)
- **🔐 API**: Status da autenticação com API SETERA (Autenticando... / 27 STR-CAM / Erro)
- **📱 Número**: Número do chip SIM (MSISDN) - obtido automaticamente ao conectar
- **📶 Sinal**: Qualidade do sinal GSM com representação visual
  - `📶 ▮▮▮▮` = Excelente (CSQ 20-31)
  - `📶 ▮▮▮▯` = Bom (CSQ 15-19)
  - `📶 ▮▮▯▯` = OK (CSQ 10-14)
  - `📶 ▮▯▯▯` = Fraco (CSQ 5-9)
  - `📵 ▯▯▯▯` = Sem sinal (CSQ 0-4 ou 99)

#### 1. Configurações (⚙️ Configurações)

- **Porta COM**: Seleção automática (lista atualiza a cada segundo)
- **Timeout Resposta**: Tempo de espera por resposta (30-300 segundos)

**Botões:**
- **🔌 Conectar/Desconectar**: Botão toggle para conectar/desconectar do Arduino/SIM800C
  - Verde "Conectar" quando desconectado
  - Vermelho "Desconectar" quando conectado
  - Validação automática após conexão (envia comando AT)
- **🧹 Limpar Log**: Limpa o log de atividades
- **💾 Exportar Log**: Salva log em arquivo .txt
- **⚡ Testar Módulo**: Executa testes de diagnóstico GSM (não bloqueia a interface)

**Recursos Automáticos:**
- ✅ Detecção automática de portas COM (atualiza a cada 1 segundo)
- ✅ Baudrate fixo em 9600 (otimizado para confiabilidade)
- ✅ Validação automática de conexão (detecta portas erradas)
- ✅ Autenticação automática com API SETERA em background
- ✅ Testes executam em background (interface não congela)

#### 2. Controle de Envios e Respostas

Gerenciar lista de comandos a enviar:

**Botões de Gerenciamento:**
- **➕ Adicionar**: Adicionar novos comandos (modo unificado)
  - **Multi-terminal selection**: Selecione 1 ou mais terminais da API
  - **"SELECIONAR TODOS"**: Opção para selecionar todos os 27 STR-CAM
  - **SIM auto-fill**: Números SIM são preenchidos automaticamente
  - **Command queue builder**: Adicione múltiplos comandos à fila
  - **Reordenação**: Use botões ▲ ▼ para reordenar comandos
  - **Terminal × Command**: 2 terminais × 3 comandos = 6 entradas criadas

- **✏️ Editar**: Editar comando selecionado

- **❌ Remover**: Remover comando(s) selecionado(s) SEM confirmação
  - **Multi-select**: Ctrl+Click para selecionar múltiplos
  - **Range select**: Shift+Click para selecionar intervalo
  - Remoção instantânea sem popup

- **❌ Remover Todos**: Remover TODOS os comandos COM confirmação
  - Mostra total de equipamentos e comandos
  - Popup de confirmação: "Esta ação NÃO pode ser desfeita!"
  - Botões: SIM / NÃO

- **📋 Importar Arquivo**: Importar lista de equipamentos em lote

**Formato de importação:**
```
Nome do Equipamento 1, +5511987654321
Nome do Equipamento 2, +5511987654322
# Linhas iniciadas com # são ignoradas
```

**Nota:** Equipamentos importados precisam ter comandos adicionados via "Adicionar" ou "Editar".

#### 3. Dialog "Adicionar Comando" (v2.2 - Unified Workflow)

Quando clica em **"➕ Adicionar"**, abre dialog com:

**Row 0: Seleção de Placas (Multi-select)**
- Lista com todos os STR-CAM da API (27 terminais)
- Opção "☑️ SELECIONAR TODOS" no topo
- Contador: "27 de 27" mostra seleção atual
- Multi-select: Ctrl+Click para múltiplos

**Row 1: Nr SIM Card (Auto-fill)**
- Exibe números SIM separados por vírgula
- Scrollable quando muitos terminais selecionados
- Máximo 80px de altura (scroll automático)
- Read-only (dados vêm da API)

**Row 2: Selecionar Comando (Dropdown)**
- Templates de comandos rápidos
- "(Nenhum - digitar manualmente)" para comandos customizados

**Row 3: Comando SMS (Input + Button)**
- Campo de texto para digitar comando
- Botão **"➕ Adicionar"** para adicionar à fila

**Row 4: Comandos a enviar (Queue Builder)**
- Lista de comandos a enviar
- Botões de controle:
  - **▲** - Move comando para cima
  - **▼** - Move comando para baixo
  - **❌** - Remove comando da fila
- Altura mínima: 150px (sempre mostra 3 botões)

**Exemplo de Uso:**
1. Selecione 3 terminais (ABC-1234, DEF-5678, GHI-9012)
2. Adicione comando 1: "CONFIG APN=internet.vivo"
3. Adicione comando 2: "$TEXT_OP:FTP_LOG:..."
4. Clique **✓ Salvar**
5. **Resultado**: 6 entradas criadas (3 terminais × 2 comandos)

**Novo em v2.2:**
- ✅ Dialog height aumentado para 750px
- ✅ SIM display com scroll (max 80px)
- ✅ Command queue com altura mínima garantida
- ✅ Todos os botões sempre visíveis

#### 4. Controles de Automação

- **▶️ INICIAR ENVIO**: Inicia envio sequencial de SMS
- **⏸️ PAUSAR**: Pausa a automação (pode ser retomada)
- **⏹️ PARAR**: Interrompe a automação completamente

**Barra de Progresso**: Mostra quantidade processada (ex: 5 / 20)

#### 5. Log de Atividades (📋 Activity Log)

Registro detalhado com código de cores:
- 🔵 **Azul**: Informações gerais
- 🟢 **Verde**: Operações bem-sucedidas
- 🟡 **Amarelo**: Avisos
- 🔴 **Vermelho**: Erros

#### 6. Sistema de Validação de Respostas

O sistema valida automaticamente as respostas SMS recebidas usando pattern matching configurável.

**Arquivo de Configuração: `command_patterns.json`**

Define tipos de comandos com padrões de validação:

```json
{
  "command_types": [
    {
      "id": "ftp_fota",
      "name": "Atualiza Firmware",
      "pattern": "$TEXT_OP:FTP_UPDATE",
      "description": "Atualização remota de firmware",
      "success_patterns": ["will download ota"],
      "failure_patterns": ["param error"],
      "case_sensitive": true
    }
  ]
}
```

**Como Funciona:**

1. **Detecção Automática de Tipo**: Ao digitar comando, o sistema detecta automaticamente o tipo baseado no pattern
2. **Validação de Resposta**: Quando SMS de resposta é recebido, verifica se contém padrões de sucesso ou falha
3. **Status Inteligente**:
   - ✅ **Sucesso**: Resposta contém padrão de sucesso
   - ❌ **Falha**: Resposta contém padrão de falha
   - ⚠️ **Resposta Desconhecida**: Resposta não corresponde a nenhum padrão

### Fluxo de Trabalho Típico

1. **Conectar Hardware**
   - Ligar Arduino + SIM800C
   - Conectar USB ao computador

2. **Iniciar Aplicação**
   - Executar `sms_automation_gui.pyw`
   - Aguardar autenticação automática com API SETERA
   - Status exibirá: "🔐 API: 27 STR-CAM"

3. **Configurar**
   - Selecionar porta COM correta (auto-detectado)
   - Clicar "🔌 Conectar"
   - Verificar status GSM (número + sinal)

4. **Adicionar Comandos (Novo Workflow v2.2)**
   - Clicar "➕ Adicionar"
   - **Selecionar múltiplos terminais** (ex: 5 câmeras)
   - **Adicionar múltiplos comandos** à fila (ex: 2 comandos)
   - Resultado: 10 entradas criadas automaticamente (5 × 2)

5. **Executar Automação**
   - Clicar "▶️ INICIAR ENVIO"
   - Acompanhar progresso na interface
   - Aguardar conclusão ou pausar se necessário

6. **Revisar Resultados**
   - Verificar status de cada comando (✅ Success / ❌ Failed)
   - Exportar log para documentação
   - Remover comandos concluídos (multi-select: Ctrl+Click)

---

## 🔧 Protocolo AT e Comandos SMS

### Sequência de Envio de SMS

```
PC → Arduino → SIM800C: AT+CMGS="+5511987654321"↵
PC ← Arduino ← SIM800C: >
PC → Arduino → SIM800C: CONFIG APN=internet.vivo
PC → Arduino → SIM800C: Ctrl+Z (byte 26)
PC ← Arduino ← SIM800C: +CMGS: 142

OK
```

### Comandos AT Utilizados

| Comando | Descrição | Resposta Esperada |
|---------|-----------|-------------------|
| `AT` | Teste básico | `OK` |
| `AT+CPIN?` | Status do chip SIM | `+CPIN: READY` |
| `AT+CSQ` | Qualidade de sinal | `+CSQ: 15,0` (0-31) |
| `AT+CREG?` | Registro na rede | `+CREG: 0,1` ou `0,5` |
| `AT+COPS?` | Operadora atual | `+COPS: 0,0,"VIVO"` |
| `AT+CNUM` | Número do SIM (MSISDN) | `+CNUM: "","<number>",129` |
| `AT+CMGF=1` | Modo texto SMS | `OK` |
| `AT+CMGS="<num>"` | Enviar SMS | `>` (prompt) |
| `AT+CMGL="ALL"` | Listar SMS recebidos | `+CMGL: ...` |

### Interpretação de Códigos

**Qualidade de Sinal (CSQ):**
- 0-9: Sinal fraco/marginal
- 10-14: OK
- 15-19: Bom
- 20-31: Excelente
- 99: Sem sinal

**Status de Registro (CREG):**
- `0,0`: Não registrado, não procurando
- `0,1`: Registrado, rede local
- `0,2`: Não registrado, procurando
- `0,3`: Registro negado
- `0,5`: Registrado, roaming

---

## 📁 Arquivos e Configurações

### Estrutura de Arquivos

```
sms-sender/
├── sms_automation_gui.pyw    # Aplicação principal Python
├── setera_api.py              # Módulo de integração com API SETERA
├── serial_bridge/
│   └── serial_bridge.ino      # Firmware Arduino
├── favicon.ico                # Ícone da aplicação
├── command_patterns.json      # Definições de tipos de comando e validação
├── sms_config.json            # Configurações (auto-gerado)
├── sms_automation.log         # Log de atividades (auto-gerado)
├── README.md                  # Este arquivo
└── CLAUDE.md                  # Documentação técnica
```

### Arquivo de Configuração (sms_config.json)

```json
{
  "port": "COM3",
  "timeout": 120,
  "cameras": [
    {
      "name": "ABC1234",
      "phone": "+5511999999999",
      "commands": [
        {
          "command": "CONFIG APN=internet.vivo",
          "command_type": "config_apn",
          "status": "pending",
          "result": ""
        },
        {
          "command": "$TEXT_OP:FTP_LOG:...",
          "command_type": "upload_log",
          "status": "pending",
          "result": ""
        }
      ]
    }
  ]
}
```

**Estrutura de Dados (v2.2):**
- Cada equipamento (`camera`) contém array de `commands`
- Cada comando tem: `command`, `command_type`, `status`, `result`
- `command_type` é detectado automaticamente ao adicionar

### API SETERA Integration (setera_api.py)

**Autenticação:**
- OAuth2 Client Credentials Flow
- Credenciais hardcoded no código
- Token obtido automaticamente em background

**Endpoint:**
```
POST https://api-manager.hgdigital.io/oauth2/token
GET  https://api.hgdigital.io/setera-core/v1/v2/terminals/find-terminal
```

**Filtro:**
- Retorna apenas terminais com `trackerModelName == "STR-CAM"`
- Ordenados por nome da placa

**Dados Retornados:**
```python
{
  'id': 123,
  'plate': 'ABC1234',
  'sim': '+5511999999999',
  'imei': '123456789012345',
  'model': 'STR-CAM',
  'company': 'SETERA'
}
```

### Log de Atividades (sms_automation.log)

Exemplo de log:
```
[22:31:16] ℹ Application started. Please connect to Arduino + SIM800C module.
[22:31:18] 🔐 Iniciando autenticação com API SETERA...
[22:31:20] ✓ API autenticada: 27 STR-CAM disponíveis
[22:32:01] ✓ Connected to Arduino + SIM800C
[22:32:05] ✓ 3 equipamento(s) adicionado(s), 6 comando(s) total
[22:32:15] ℹ Processing Camera 1: ABC1234 (Command 1/2)
[22:32:45] ✓ SMS sent to camera 1
[22:33:05] ✓ Received SMS response from camera 1
```

---

## 🐛 Solução de Problemas

### Problemas Comuns

#### 1. Aplicação não conecta ao Arduino / Validação Falhou

**Sintomas:**
- Erro: "Validação Falhou"
- Status: "● Validação Falhou"
- Log: "✗ Módulo não responde aos comandos AT"

**Soluções:**
1. Verificar porta COM correta no dropdown
2. Verificar Arduino está conectado via USB
3. Verificar alimentação do SIM800C (LED deve estar aceso)
4. Testar com Arduino IDE Serial Monitor (enviar "AT", esperar "OK")
5. Fechar outros programas que usam a porta (Arduino IDE, PuTTY)

#### 2. API SETERA não autentica

**Sintomas:**
- Status: "🔐 API: Erro de autenticação"
- Dropdown de placas vazio

**Soluções:**
1. Verificar conexão com internet
2. Verificar credenciais API em `setera_api.py`
3. Consultar logs para detalhes do erro
4. Sistema funciona offline (entrada manual)

#### 3. Módulo SIM800C não responde

**Sintomas:**
- Comando AT retorna vazio
- Timeout em todos os comandos

**Soluções:**
- Verificar **jumpers em D0/D1** (NÃO D6/D7!)
- Confirmar alimentação adequada (2A+ durante transmissão)
- Verificar firmware foi carregado no Arduino
- Pressionar botão "To Start" no shield por 2-3 segundos

#### 4. Sinal GSM fraco ou ausente

**Sintomas:**
- `AT+CSQ` retorna valores baixos (< 10) ou 99
- SMS não são enviados

**Soluções:**
- Mover para local com melhor cobertura
- Verificar conexão da antena GSM
- Confirmar operadora tem cobertura na região

#### 5. Multi-select não funciona

**Sintomas:**
- Só seleciona 1 terminal por vez
- Ctrl+Click não funciona

**Soluções:**
- Usar **Ctrl+Click** para seleções individuais
- Usar **Shift+Click** para intervalos
- Verificar está clicando em área do texto (não scrollbar)

---

## 📊 Novidades da Versão 2.3

### Smart Time Display
- ✅ **Tempo movido para coluna Status** - Tempo de resposta agora aparece após o status
- ✅ **Formatação inteligente de tempo** - Unidades simplificadas baseadas na duração:
  - `< 1 minuto` → `Xs` (ex: `45s`)
  - `< 1 hora` → `XmYs` (ex: `2m15s`)
  - `< 1 dia` → `XhYm` (ex: `1h30m`)
  - `> 1 dia` → `XdYh` (ex: `2d5h`)
- ✅ **Coluna Resposta limpa** - Mostra apenas o conteúdo da mensagem SMS
- ✅ **Exemplo de display**: `✅ Sucesso (49s)` ou `❌ Falha (2m15s)`

### Column Layout Optimization
- ✅ **Proporção 30:70** - Coluna Comando (30%) e Resposta (70%)
- ✅ **Comando mostra texto real** - Exibe o comando completo, não apenas o tipo
- ✅ **Ambas colunas expansíveis** - Redimensionamento dinâmico

### Manual Entry Enhancement
- ✅ **Botão "Entrada Manual"** - Permite adicionar terminal manualmente quando API disponível
- ✅ **Popup otimizado** - Altura 250px com favicon
- ✅ **Smart country code** - Adiciona +55 automaticamente se usuário não incluir +
- ✅ **Auto-integração** - Terminal adicionado automaticamente à lista e selecionado

---

## 📊 Novidades da Versão 2.2

### Integração com API SETERA
- ✅ Autenticação automática OAuth2 em background
- ✅ Busca automática de terminais STR-CAM
- ✅ Auto-fill de números SIM (previne erros de digitação)
- ✅ Indicador de status da API no header
- ✅ Fallback para entrada manual se API indisponível

### Unified Command Queue Builder
- ✅ Dialog único para adicionar comandos
- ✅ Multi-terminal selection (Ctrl+Click, Shift+Click)
- ✅ Opção "SELECIONAR TODOS" (27 STR-CAM de uma vez)
- ✅ Command queue com reordenação (▲ ▼ buttons)
- ✅ Terminal × Command multiplication (3 × 2 = 6 entradas)
- ✅ SIM display com scroll (max 80px height)
- ✅ Command queue altura mínima (150px - sempre mostra 3 botões)
- ✅ Dialog height aumentado (750px para acomodar todos os elementos)

### Multi-Select Deletion
- ✅ Treeview com `selectmode='extended'`
- ✅ Ctrl+Click para seleção múltipla
- ✅ Shift+Click para seleção por intervalo
- ✅ Botão "Remover" SEM confirmação (remoção rápida)
- ✅ Botão "Remover Todos" COM confirmação (segurança)
- ✅ Log detalhado: "5 comando(s) removido(s), 2 equipamento(s) deletado(s)"

### UX Improvements
- ✅ Ícones uniformes (🧹 para limpar, ❌ para remover)
- ✅ Espaçamento consistente entre ícone e texto
- ✅ Botões com larguras otimizadas
- ✅ Hover effects uniformes (outline → filled)
- ✅ Melhor layout do dialog (sem cortes de texto)

### Duplicate Handling
- ✅ Sistema inteligente: se terminal já existe, ADICIONA comando à fila
- ✅ Se terminal não existe, CRIA novo com comando
- ✅ Permite múltiplos comandos para mesmo terminal
- ✅ Log informativo: "3 equipamento(s) novo(s), 6 comando(s) total adicionado(s)"

---

## 🛠️ Desenvolvimento

### Tecnologias Utilizadas

- **Python 3.8+**
- **ttkbootstrap** - Interface gráfica moderna
- **pyserial** - Comunicação serial
- **requests** - HTTP client para API
- **threading** - Processamento assíncrono
- **queue** - Comunicação entre threads
- **json** - Persistência de configurações
- **Arduino C++** - Firmware do bridge

### Arquitetura de Software

#### Padrão de Threading

```python
Main Thread (GUI)
    ├─ Gerencia interface tkinter
    ├─ Responde a eventos do usuário
    ├─ Atualiza elementos visuais
    ├─ Autentica com API SETERA
    └─ Envia comandos via message_queue

Worker Thread (SerialWorker)
    ├─ Processa comandos da fila
    ├─ Comunica com serial (Arduino)
    ├─ Interpreta respostas AT
    └─ Retorna resultados via log_queue

API Thread (Background)
    ├─ Autentica com API SETERA
    ├─ Busca terminais STR-CAM
    └─ Atualiza cache de terminais
```

#### Estado dos Comandos

```
PENDING → SENDING → WAITING → SUCCESS
                             → FAILED
                             → UNKNOWN_RESPONSE
                             → SKIPPED
```

---

## 📝 Licença e Créditos

**Copyright © 2025 SETERA**
Todos os direitos reservados.

### Parte do SETERA Tools Suite

Este software faz parte do conjunto de ferramentas SETERA para desenvolvimento e configuração de rastreadores GPS STR1010/STR1010Plus/STR2020.

**Ferramentas relacionadas:**
- ConfigSTR1010 - Configuração de rastreadores
- Serial Monitor (1ch/2ch/4ch) - Monitoramento serial
- Protocol Parsers - Análise de protocolos
- Firmware Updater - Atualização de firmware

---

## 📞 Suporte

Para suporte técnico ou dúvidas:

- **Equipe de Desenvolvimento SETERA**
- **GitHub Issues** (para contribuidores do repositório)
- **Documentação Técnica**: Consulte `CLAUDE.md` para detalhes de arquitetura

---

## 📋 Changelog

### Versão 2.3 - 20/Out/2025
- ✅ **Smart Time Display** - Tempo movido para coluna Status com formatação inteligente
- ✅ **Column Layout 30:70** - Otimização da proporção Comando/Resposta
- ✅ **Comando mostra texto real** - Exibe comando completo ao invés do tipo
- ✅ **Coluna Resposta limpa** - Sem prefixos, apenas conteúdo da mensagem
- ✅ **Manual Entry button** - Entrada manual disponível mesmo com API ativa
- ✅ **Popup height fix** - Manual entry dialog com 250px
- ✅ **Smart +55 logic** - Adiciona country code automaticamente se necessário
- ✅ **format_elapsed_time() function** - Formatação de tempo com unidades simplificadas

### Versão 2.2 - 20/Out/2025
- ✅ **Integração com API SETERA** - OAuth2 authentication em background
- ✅ **Multi-terminal selection** - Selecione múltiplos STR-CAM de uma vez
- ✅ **Command Queue Builder** - Adicione múltiplos comandos por operação
- ✅ **Terminal × Command multiplication** - 3 terminais × 2 comandos = 6 entradas
- ✅ **Auto-fill SIM numbers** - Previne erros de digitação
- ✅ **Multi-select deletion** - Remova múltiplos comandos com Ctrl+Click
- ✅ **"Remover Todos" button** - Limpa lista completa com confirmação
- ✅ **Dialog layout improvements** - Height 750px, scrollable SIM display
- ✅ **Unified workflow** - Um único botão "Adicionar" para tudo
- ✅ **Ícones consistentes** - 🧹 limpar, ❌ remover
- ✅ **Duplicate handling** - Adiciona comandos a terminais existentes
- ✅ **API status indicator** - Mostra quantidade de STR-CAM disponíveis
- ✅ Removido botão "Adicionar Comando" (unificado no "Adicionar")
- ✅ Título atualizado: "Sistema Automatizado de Envio de Comandos SMS"

### Versão 2.1 - 19/Out/2025
- ✅ Implementação inicial da API integration
- ✅ Dropdown searchable para seleção de placas
- ✅ Auto-fill de números SIM

### Versão 1.3 - 19/Out/2025
- ✅ **Sistema inteligente de validação de respostas** com pattern matching configurável
- ✅ **Comandos individuais por dispositivo** (removido campo de comando global)
- ✅ **Arquivo command_patterns.json** para configuração de tipos de comando
- ✅ **Detecção automática de tipo de comando** no diálogo Add/Edit
- ✅ **Novo status UNKNOWN_RESPONSE** - continua aguardando após resposta desconhecida
- ✅ **Mudança de Hardware Serial**: Jumpers agora em D0/D1 (não mais D6/D7)
- ✅ **Hardware Serial1 no firmware**: Substitui SoftwareSerial (mais confiável no R4)

### Versão 1.2 - 17/Out/2025
- ✅ Interface traduzida para português brasileiro
- ✅ Baudrate fixo em 9600 (otimizado para confiabilidade)
- ✅ Detecção automática de portas COM (atualização a cada 1 segundo)
- ✅ **Botão toggle Conectar/Desconectar**
- ✅ **Validação automática de conexão**
- ✅ **Display do número do chip SIM (MSISDN)**
- ✅ **Indicador visual de força do sinal (CSQ)** com barras gráficas

### Versão 1.1
- Suporte a Arduino Uno R4
- Melhorias no sistema de logs

### Versão 1.0
- Lançamento inicial
- Interface gráfica com ttkbootstrap
- Automação de envio de SMS

---

**SETERA - Sistema Automatizado de Envio de Comandos SMS v2.3**
*Desenvolvido com ❤️ para simplificar a configuração de frotas GPS*
