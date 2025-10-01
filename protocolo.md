# Protocolo de Comunicação STR1010+

Este documento descreve o protocolo de comunicação completo do dispositivo STR1010+ para integração com plataformas de rastreamento GPS.

**Versão do Firmware:** 1.2.8 (128)
**Porta de Comunicação:** UART1 (Única porta de interface - bidirecional)
**Direção de Dados:**
- **RX (Recebe):** Comandos de configuração (CMD,...)
- **TX (Envia):** Respostas (CMD,OK / TOSERVER), dados automáticos (FR1, TPMS, DRV), alarmes (ALM)
**Formato:** Todos os comandos e mensagens terminam com asterisco (*)

---

## RESUMO - REFERÊNCIA RÁPIDA

### Comandos Enviados ao Dispositivo

#### Configuração e Sistema
| Comando | Descrição |
|---------|-----------|
| `CMD,CFGGET*` | Obter todas as configurações |
| `CMD,CFGSET,<params>*` | Definir múltiplas configurações |
| `CMD,FWGET*` | Obter versão do firmware |
| `CMD,PVDGET*` | Obter status do monitor de tensão |
| `CMD,HEALTHGET*` | Obter diagnósticos do sistema |
| `CMD,REBOOT*` | Reiniciar dispositivo |
| `CMD,MEM_CLR*` | Reset de fábrica |

#### Motoristas
| Comando | Descrição |
|---------|-----------|
| `CMD,DRVGET*` | Obter todos os IDs de motorista |
| `CMD,DRVADD,<id>*` | Adicionar motorista |
| `CMD,DRVDEL,<id>*` | Remover motorista |
| `CMD,DRVCOUNT*` | Contar motoristas cadastrados |
| `CMD,DRVDELALL*` | Remover todos os motoristas |

#### Códigos de Atividade
| Comando | Descrição |
|---------|-----------|
| `CMD,ACTGET*` | Obter todos os códigos de atividade |
| `CMD,ACTADD,<codigo>*` | Adicionar código de atividade |
| `CMD,ACTDEL,<codigo>*` | Remover código de atividade |
| `CMD,ACTDELALL*` | Remover todos os códigos de atividade |

#### TPMS (Sensores de Pressão)
| Comando | Descrição |
|---------|-----------|
| `CMD,TPMSGET*` | Obter configurações de sensores TPMS |
| `CMD,TPMS,<id>,<press_min>,<press_max>,<temp_min>,<temp_max>*` | Configurar sensor TPMS |
| `CMD,TPMSDEL,<id>*` | Remover sensor TPMS |
| `CMD,TPMSCOUNT*` | Contar sensores TPMS cadastrados |
| `CMD,TPMSDELALL*` | Remover todos os sensores TPMS |

#### Geocercas
| Comando | Descrição |
|---------|-----------|
| `CMD,GEOCGET*` | Obter geocercas circulares |
| `CMD,GEORGET*` | Obter geocercas retangulares |
| `CMD,GEOPGET*` | Obter geocercas poligonais |
| `CMD,GEOC,<codigo>,<in_out>,<vel_max>,<lat>,<long>,<raio>*` | Configurar geocerca circular |
| `CMD,GEOR,<codigo>,<in_out>,<vel_max>,<lat1>,<long1>,<lat2>,<long2>*` | Configurar geocerca retangular |
| `CMD,GEOP,<codigo>,<in_out>,<vel_max>,<vertices>*` | Configurar geocerca poligonal |
| `CMD,GEODEL,<codigo>*` | Remover geocerca |
| `CMD,GEOCDELALL*` | Remover todas as geocercas circulares |
| `CMD,GEORDELALL*` | Remover todas as geocercas retangulares |
| `CMD,GEOPDELALL*` | Remover todas as geocercas poligonais |

#### Configurações Específicas
| Comando | Descrição |
|---------|-----------|
| `CMD,CFG,DRIVER,<0\|1>*` | Habilitar alarme motorista não identificado |
| `CMD,CFG,ENGCUT,<enabled>,<idle_time>,<min_time>*` | Configurar corte motor ocioso |
| `CMD,CFG,RPM,<params>*` | Configurar zonas de RPM |
| `CMD,CFG,RPMDEF,<params>*` | Configurar RPM padrão |
| `CMD,CFG,RPMLIM,<params>*` | Configurar limites de RPM |
| `CMD,CFG,TURBO,<max_pressure>*` | Configurar pressão máxima turbo |
| `CMD,CFG,TURBODEF,<value>*` | Configurar turbo padrão |
| `CMD,CFG,ENGTEMP,<max_temp>*` | Configurar temperatura máxima motor |
| `CMD,CFG,FUELOUT,<threshold>*` | Configurar limiar saída combustível |
| `CMD,CFG,FUELIN,<threshold>*` | Configurar limiar entrada combustível |
| `CMD,CFG,SPEED,<factor>*` | Configurar conversão velocidade |
| `CMD,CFG,KEYBOARD,<0\|1>*` | Definir modo do teclado (0 = LCD, 1 = RFID) |
| `CMD,CFG,UART,<porta>,<baud>,<bits>,<stop>,<flow>*` | Ajustar parâmetros das portas seriais 2-6 |
| `CMD,CFG,TXT,UART,<porta>,<dados>*` | Encaminhar texto para uma UART periférica |
| `CMD,CFG,ROLL,<angle>*` | Configurar ângulo capotamento |
| `CMD,CFG,DHL,<params>*` | Configurar descida ponto morto |
| `CMD,CFG,PULSE,<enabled>*` | Habilitar modo pulso |
| `CMD,CFG,VEL,<params>*` | Configurar faixas velocidade |
| `CMD,CFG,IN,<port>,<params>*` | Configurar entrada digital (IN3-IN10) |
| `CMD,OUT,<port>,<state>*` | Controlar saída digital (OUT2-OUT5) |
| `CMD,CFG,RPM_CLR*` | Limpar contadores RPM |
| `CMD,CFG,TURBO_CLR*` | Limpar contador turbo |
| `CMD,CFG,ENG_CLR*` | Limpar contadores motor |
| `CMD,MP3,<codigo_hex>*` | Acionar reprodução sonora (módulo MP3) |
| `CMD,SMS,<mensagem>*` | Exibir mensagem no teclado LCD (até 32 caracteres) |
| `ODO_CLR*` | Limpar odômetro |
#### Debug/Log
| Comando | Descrição |
|---------|-----------|
| `LOG_GPS*` | Ativar log GPS |
| `LOG_CAN*` | Ativar log CAN |
| `LOG_KEYBOARD*` | Ativar log teclado/RFID |
| `LOG_TILT*` | Ativar log sensor inclinação |
| `LOG_OFF*` | Desativar todos os logs |

---

### Respostas do Dispositivo

#### Respostas a Comandos (TOSERVER)
| Resposta | Descrição |
|----------|-----------|
| `CMD,OK*` | Comando executado com sucesso |
| `TOSERVER,STARTUP*` | Mensagem de inicialização |
| `TOSERVER,RPMVD,...*` | Resposta completa CFGGET |
| `TOSERVER,FW<versao>*` | Versão do firmware |
| `TOSERVER,PVD,<estado>,<tempo>,<seguro>*` | Status monitor tensão |
| `TOSERVER,HEALTH,<diagnosticos>*` | Diagnósticos sistema (uptime, heap, tasks, slots) |
| `TOSERVER,<driver_ids>*` | Lista de IDs motoristas (DRVGET) |
| `TOSERVER,DRVCOUNT,<qtd>*` | Contagem motoristas |
| `TOSERVER,<activity_codes>*` | Lista códigos atividade (ACTGET) |
| `TOSERVER,<tpms_data>*` | Configurações sensores TPMS |
| `TOSERVER,TPMSCOUNT,<qtd>*` | Contagem sensores TPMS |
| `TOSERVER,<payload>*` | Encaminhamento bruto de mensagens CAN não regulares (CAR, LIMITS, REBOOT, VERSION, @MODE, CONFIG, DEBUG, RAPIDS) |

_Observação: em caso de parâmetros inválidos o equipamento pode permanecer silencioso (não há `CMD,ERROR*`)._
### Dados Transmitidos Automaticamente

#### Dados de CAN Bus
| Formato | Descrição |
|---------|-----------|
| `FR1,<45_campos>*` | Dados veículo CAN (500ms, motor ligado) |

**Principais campos FR1:**
- Estado motor (0=Off, 1=Aux, 2=On)
- Odômetro, velocidade, RPM
- Temperaturas (motor, óleo, água)
- Combustível, pressão turbo
- Contadores RPM (verde, amarelo, vermelho)
- Descida ponto morto
- Ângulos (roll, pitch)
- Estados IN3-IN10, OUT2-OUT5

#### Dados de TPMS
| Formato | Descrição |
|---------|-----------|
| `TPMS,<id>\|<alarme>\|<pressao>\|<temperatura>*` | Dados sensor TPMS |

**Códigos alarme TPMS:**
- 0=Normal
- 1=Pressão fora limites
- 2=Temperatura fora limites
- 3=Pressão E temperatura fora
- 4=Bateria baixa
- 5-7=Bateria baixa + outros alarmes

#### Identificação Motorista/Atividade
| Formato | Descrição |
|---------|-----------|
| `DRV,<id_motorista>,ACT,<codigo_atividade>*` | Identificação completa motorista |

---

### Alarmes (ALM)

| Código | Descrição | Formato Dados |
|--------|-----------|---------------|
| `ALM,101,<velocidade>*` | Excesso de velocidade (faixa 1) | Velocidade atual |
| `ALM,102,<velocidade>*` | Excesso de velocidade (faixa 2) | Velocidade atual |
| `ALM,103,<velocidade>*` | Excesso velocidade em geocerca | Velocidade atual |
| `ALM,104,<codigo>*` | Entrada em geocerca | Código da cerca |
| `ALM,105,<codigo>*` | Saída de geocerca | Código da cerca |
| `ALM,106,<pressao>*` | Pressão turbo acima limite | Pressão turbo |
| `ALM,107,<contador>*` | Descida ponto morto | Contador |
| `ALM,108,<nivel>*` | Saída combustível detectada | Nível combustível |
| `ALM,109,<nivel>*` | Entrada combustível detectada | Nível combustível |
| `ALM,110,<roll>*` | Inclinação lateral acima do limite | Ângulo (graus) |
| `ALM,111,<temperatura>*` | Temperatura motor acima limite | Temperatura |
| `ALM,112,<rpm>*` | RPM acima limite | RPM |
| `ALM,113,<velocidade>*` | Motorista não identificado | Velocidade atual |
| `ALM,114,1*` | Corte motor ocioso ativado | Sempre 1 |
| `ALM,124,<estado>*` | Mudança estado IN4 | 0 ou 1 |
| `ALM,125,<estado>*` | Mudança estado IN5 | 0 ou 1 |
| `ALM,126,<estado>*` | Mudança estado IN6 | 0 ou 1 |
| `ALM,127,<estado>*` | Mudança estado IN7 | 0 ou 1 |
| `ALM,128,<estado>*` | Mudança estado IN8 | 0 ou 1 |
| `ALM,129,<estado>*` | Mudança estado IN9 | 0 ou 1 |
| `ALM,130,<estado>*` | Mudança estado IN10 | 0 ou 1 |
| `ALM,142,<estado>*` | Mudança estado OUT2 | 0 ou 1 |
| `ALM,143,<estado>*` | Mudança estado OUT3 | 0 ou 1 |
| `ALM,144,<estado>*` | Mudança estado OUT4 | 0 ou 1 |
| `ALM,145,<estado>*` | Mudança estado OUT5 | 0 ou 1 |

---

## 1. COMANDOS E RESPOSTAS

Todos os comandos seguem o formato: `CMD,<comando>,<parâmetros>*`
Todas as respostas seguem o formato: `TOSERVER,<tipo>,<dados>*`

### 1.1 Comandos de Configuração Geral

#### CMD,CFGGET*
**Descrição:** Obtém todas as configurações do dispositivo.

**Resposta:**  `CMD,OK*` 
```
TOSERVER,RPMVD,<rpm_green_min>,<rpm_green_max>,RPMAM,<rpm_yellow_min>,<rpm_yellow_max>,RPMVM,<rpm_red_min>,<rpm_red_max>,DHL,<downhill_enabled>,<downhill_rpm_max>,<downhill_speed_min>,<downhill_seconds_min>,RPMMAX,<rpm_max>,ENGTEMP,<temperature_engine_max>,TURBO,<turbo_pressure_max>,PULSE,<pulse_enabled>,SPEED,<speed_type>,VEL1,<vel1_min>,<vel1_max>,<vel1_count>,<vel1_beep>,VEL2,<vel2_min>,<vel2_max>,<vel2_count>,<vel2_beep>,DHL_STATUS,<dhl_status>,RPMDEF,<rpm_def_min>,<rpm_def_max>,<rpm_def_beep>,<rpm_def_enabled>,TURBODEF,<turbo_def_value>,FUELOUT,<fuel_threshold_out>,FUELIN,<fuel_threshold_in>,ROLL,<rollover_alarm_angle>,IN3,<in3_level>,<in3_enabled>,<in3_notify_when_enabled>,<in3_notify_when_disabled>,<in3_beep>,IN4,<in4_level>,<in4_enabled>,<in4_notify_when_enabled>,<in4_notify_when_disabled>,<in4_beep>,IN5,<in5_level>,<in5_enabled>,<in5_notify_when_enabled>,<in5_notify_when_disabled>,<in5_beep>,IN6,<in6_level>,<in6_enabled>,<in6_notify_when_enabled>,<in6_notify_when_disabled>,<in6_beep>,IN7,<in7_level>,<in7_enabled>,<in7_notify_when_enabled>,<in7_notify_when_disabled>,<in7_beep>,IN8,<in8_level>,<in8_enabled>,<in8_notify_when_enabled>,<in8_notify_when_disabled>,<in8_beep>,IN9,<in9_level>,<in9_enabled>,<in9_notify_when_enabled>,<in9_notify_when_disabled>,<in9_beep>,IN10,<in10_level>,<in10_enabled>,<in10_notify_when_enabled>,<in10_notify_when_disabled>,<in10_beep>,UNIDENTIFIED_DRIVER,<unidentified_driver_alarm_enabled>,IDLE_ENGCUT,<idle_engine_cut_enabled>,<idle_engine_cut_timer>,<idle_engine_cut_period>*
```

**Campos:**
- `RPMVD`: Zona verde de RPM (mínimo e máximo)
- `RPMAM`: Zona amarela de RPM
- `RPMVM`: Zona vermelha de RPM
- `DHL`: Configurações de descida em ponto morto (downhill)
- `RPMMAX`: RPM máximo para alarme
- `ENGTEMP`: Temperatura máxima do motor
- `TURBO`: Pressão máxima do turbo
- `PULSE`: Modo de conversão de pulso
- `SPEED`: Tipo de velocidade (0=GPS, 1=CAN)
- `VEL1/VEL2`: Configurações de velocidade (faixas 1 e 2)
- `ROLL`: Ângulo de capotamento
- `IN3-IN10`: Configurações das entradas digitais
- `UNIDENTIFIED_DRIVER`: Alarme de motorista não identificado
- `IDLE_ENGCUT`: Corte de motor ocioso

**Exemplo:**
```
TOSERVER,RPMVD,1000,1500,RPMAM,1500,2000,RPMVM,2000,3000,DHL,1,800,30,5,RPMMAX,3500,ENGTEMP,110,TURBO,200,PULSE,0,SPEED,1,VEL1,0,80,0,1,VEL2,80,120,0,1,DHL_STATUS,0,RPMDEF,1200,1800,1,1,TURBODEF,150,FUELOUT,5,FUELIN,5,ROLL,45,IN3,0,1,1,0,1,IN4,0,1,1,0,1,IN5,0,0,0,0,0,IN6,0,0,0,0,0,IN7,0,0,0,0,0,IN8,0,0,0,0,0,IN9,0,0,0,0,0,IN10,0,0,0,0,0,UNIDENTIFIED_DRIVER,1,IDLE_ENGCUT,1,180,10*
```

#### CMD,CFGSET,<todos_os_parametros>*
**Descrição:** Define múltiplas configurações de uma vez. Usa o mesmo formato da resposta CFGGET.

**Resposta:**  `CMD,OK*` 

---

### 1.2 Comandos de Firmware e Sistema

#### CMD,FWGET*
**Descrição:** Obtém a versão do firmware.

**Resposta:**  `CMD,OK*` 
```
TOSERVER,FW<versao>*
```

**Exemplo:**
```
TOSERVER,FW128*
```

#### CMD,PVDGET*
**Descrição:** Obtém o status do monitor de tensão PVD (Power Voltage Detection).

**Resposta:**  `CMD,OK*` 
```
TOSERVER,PVD,<estado>,<tempo_estavel>,<tensao_segura>*
```

**Campos:**
- `estado`: Estado do PVD ("SAFE", "WARNING", "CRITICAL", "UNKNOWN")
- `tempo_estavel`: Tempo em ms que a tensão está estável
- `tensao_segura`: 1 se tensão segura, 0 caso contrário

**Exemplo:**
```
TOSERVER,PVD,SAFE,5000,1*
```

#### CMD,HEALTHGET*
**Descrição:** Obtém diagnósticos completos do sistema incluindo status de slots duplos (v1.2.8+).

**Resposta:**  `CMD,OK*` 
```
TOSERVER,HEALTH,<uptime>,<heap_usado>,<heap_livre>,<heap_total>,<tasks>,<queue_ok>,<pvd_ok>,<wd_ok>,<slot0_ok>,<slot0_seq>,<slot1_ok>,<slot1_seq>,<slot_ativo>*
```

**Campos:**
- `uptime`: Tempo desde inicialização (segundos)
- `heap_usado`: Memória heap usada (bytes)
- `heap_livre`: Memória heap livre (bytes)
- `heap_total`: Memória heap total (bytes)
- `tasks`: Número de tarefas ativas
- `queue_ok`: Status das filas (1=OK, 0=Erro)
- `pvd_ok`: Status do monitor de tensão (1=OK, 0=Erro)
- `wd_ok`: Status do watchdog (1=OK, 0=Erro)
- `slot0_ok`: Slot 0 válido (1=Sim, 0=Não)
- `slot0_seq`: Número de sequência do slot 0
- `slot1_ok`: Slot 1 válido (1=Sim, 0=Não)
- `slot1_seq`: Número de sequência do slot 1
- `slot_ativo`: Slot atualmente ativo (0 ou 1)

**Exemplo:**
```
TOSERVER,HEALTH,3600,25000,15000,40000,12,1,1,1,1,150,1,151,1*
```

#### CMD,REBOOT*
**Descrição:** Reinicia o dispositivo.

**Resposta:**  `CMD,OK*` 

#### CMD,MEM_CLR*
**Descrição:** Reset de fábrica - apaga AMBOS os slots de configuração e reinicia.

**Resposta:**  `CMD,OK*` 

---

### 1.3 Comandos de Motoristas

#### CMD,DRVGET*
**Descrição:** Obtém todos os IDs de motorista cadastrados (máximo 80 por resposta).

**Resposta:**  `CMD,OK*` 
```
TOSERVER,<id1>,<id2>,...,<idN>*
```

**Campos:**
- IDs de motorista com 11 caracteres cada

**Exemplo:**
```
TOSERVER,12345678901,98765432109,11122233344*
```

#### CMD,DRVADD,<id>*
**Descrição:** Adiciona um novo ID de motorista.

**Parâmetros:**
- `id`: ID do motorista (11 caracteres)

**Resposta:**  `CMD,OK*` 

**Exemplo:**
```
CMD,DRVADD,12345678901*
```

#### CMD,DRVDEL,<id>*
**Descrição:** Remove um ID de motorista.

**Parâmetros:**
- `id`: ID do motorista a ser removido

**Resposta:**  `CMD,OK*` 

#### CMD,DRVCOUNT*
**Descrição:** Obtém a contagem de motoristas cadastrados.

**Resposta:**  `CMD,OK*` 
```
TOSERVER,DRVCOUNT,<quantidade>*
```

**Exemplo:**
```
TOSERVER,DRVCOUNT,15*
```

#### CMD,DRVDELALL*
**Descrição:** Remove todos os motoristas cadastrados.

**Resposta:**  `CMD,OK*` 
```
TOSERVER,DRVCOUNT,0*
```

---

### 1.4 Comandos de Códigos de Atividade

#### CMD,ACTGET*
**Descrição:** Obtém todos os códigos de atividade cadastrados.

**Resposta:**  `CMD,OK*` 
```
TOSERVER,<cod1>,<cod2>,...,<codN>*
```

**Campos:**
- Códigos de atividade com 2 caracteres cada

**Exemplo:**
```
TOSERVER,01,02,03,10,15*
```

#### CMD,ACTADD,<codigo>*
**Descrição:** Adiciona um novo código de atividade.

**Parâmetros:**
- `codigo`: Código de atividade (2 caracteres)

**Resposta:**  `CMD,OK*` 

#### CMD,ACTDEL,<codigo>*
**Descrição:** Remove um código de atividade.

**Resposta:**  `CMD,OK*` 

#### CMD,ACTDELALL*
**Descrição:** Remove todos os códigos de atividade.

**Resposta:**  `CMD,OK*` 

---

### 1.5 Comandos de TPMS (Tire Pressure Monitoring System)

#### CMD,TPMSGET*
**Descrição:** Obtém todas as configurações de sensores TPMS (até ~1100 bytes).

**Resposta:**  `CMD,OK*` 
```
TOSERVER,<sensor1_data>,<sensor2_data>,...*
```

**Formato de cada sensor:**
```
<id_sensor>,<pressao_min>,<pressao_max>,<temperatura_min>,<temperatura_max>
```

**Campos:**
- `id_sensor`: ID do sensor TPMS (12 caracteres hexadecimais)
- `pressao_min`: Pressão mínima (kPa)
- `pressao_max`: Pressão máxima (kPa)
- `temperatura_min`: Temperatura mínima (°C)
- `temperatura_max`: Temperatura máxima (°C)

**Exemplo:**
```
TOSERVER,1A2B3C4D5E6F,180,250,-10,80,9F8E7D6C5B4A,180,250,-10,80*
```

#### CMD,TPMS,<id>,<press_min>,<press_max>,<temp_min>,<temp_max>*
**Descrição:** Configura um sensor TPMS.

**Parâmetros:**
- `id`: ID do sensor (12 caracteres hex)
- `press_min`: Pressão mínima (kPa)
- `press_max`: Pressão máxima (kPa)
- `temp_min`: Temperatura mínima (°C)
- `temp_max`: Temperatura máxima (°C)

**Resposta:**  `CMD,OK*` 

#### CMD,TPMSDEL,<id>*
**Descrição:** Remove um sensor TPMS.

**Resposta:**  `CMD,OK*` 

#### CMD,TPMSCOUNT*
**Descrição:** Obtém a contagem de sensores TPMS cadastrados.

**Resposta:**  `CMD,OK*` 
```
TOSERVER,TPMSCOUNT,<quantidade>*
```

#### CMD,TPMSDELALL*
**Descrição:** Remove todos os sensores TPMS.

**Resposta:**  `CMD,OK*` 
```
TOSERVER,TPMSCOUNT,0*
```

---

### 1.6 Comandos de Geocercas (Geofences)

**Nota:** Para obter todas as geocercas, deve-se executar GEOCGET, GEORGET e GEOPGET individualmente.

#### CMD,GEOCGET*
**Descrição:** Obtém todas as geocercas circulares.

**Resposta:**  `CMD,OK*` 
```
TOSERVER,GEOC,<cerca1>,<cerca2>,...*
```

**Formato de cada cerca:**
```
<codigo>,<in_out>,<velocidade_max>,<latitude_centro>,<longitude_centro>,<raio>
```

**Campos:**
- `codigo`: Código da cerca (4 caracteres)
- `in_out`: 1=Alarme na entrada, 0=Alarme na saída
- `velocidade_max`: Velocidade máxima permitida (km/h)
- `latitude_centro`: Latitude do centro (graus decimais)
- `longitude_centro`: Longitude do centro (graus decimais)
- `raio`: Raio em metros

**Exemplo:**
```
TOSERVER,GEOC,C001,1,60,-23.5505,-46.6333,500,C002,0,80,-23.5600,-46.6400,1000*
```

#### CMD,GEORGET*
**Descrição:** Obtém todas as geocercas retangulares.

**Resposta:**  `CMD,OK*` 
```
TOSERVER,GEOR,<cerca1>,<cerca2>,...*
```

**Formato de cada cerca:**
```
<codigo>,<in_out>,<velocidade_max>,<lat_superior_esq>,<long_superior_esq>,<lat_inferior_dir>,<long_inferior_dir>
```

**Campos:**
- `codigo`: Código da cerca (4 caracteres)
- `in_out`: 1=Alarme na entrada, 0=Alarme na saída
- `velocidade_max`: Velocidade máxima permitida (km/h)
- `lat_superior_esq`: Latitude do canto superior esquerdo
- `long_superior_esq`: Longitude do canto superior esquerdo
- `lat_inferior_dir`: Latitude do canto inferior direito
- `long_inferior_dir`: Longitude do canto inferior direito

**Exemplo:**
```
TOSERVER,GEOR,R001,1,60,-23.5500,-46.6350,-23.5510,-46.6320*
```

#### CMD,GEOPGET*
**Descrição:** Obtém todas as geocercas poligonais. Cada polígono é enviado em mensagem separada.

**Resposta (uma por polígono):**
```
TOSERVER,GEOP,<codigo>,<in_out>,<velocidade_max>,<lat1>,<long1>,<lat2>,<long2>,...,<latN>,<longN>*
```

**Campos:**
- `codigo`: Código da cerca (4 caracteres)
- `in_out`: 1=Alarme na entrada, 0=Alarme na saída
- `velocidade_max`: Velocidade máxima permitida (km/h)
- `lat1,long1...latN,longN`: Coordenadas dos vértices (até 20 vértices)

**Exemplo:**
```
TOSERVER,GEOP,P001,1,50,-23.5500,-46.6350,-23.5505,-46.6340,-23.5510,-46.6345,-23.5505,-46.6355*
```

#### CMD,GEOC,<codigo>,<in_out>,<vel_max>,<lat_centro>,<long_centro>,<raio>*
**Descrição:** Adiciona ou atualiza uma geocerca circular.

**Resposta:**  `CMD,OK*` 

**Exemplo:**
```
CMD,GEOC,C001,1,60,-23.5505,-46.6333,500*
```

#### CMD,GEOR,<codigo>,<in_out>,<vel_max>,<lat_sup_esq>,<long_sup_esq>,<lat_inf_dir>,<long_inf_dir>*
**Descrição:** Adiciona ou atualiza uma geocerca retangular.

**Resposta:**  `CMD,OK*` 

#### CMD,GEOP,<codigo>,<in_out>,<vel_max>,<lat1>,<long1>,...,<latN>,<longN>*
**Descrição:** Adiciona ou atualiza uma geocerca poligonal (até 20 vértices).

**Resposta:**  `CMD,OK*` 

#### CMD,GEODEL,<codigo>*
**Descrição:** Remove uma geocerca (qualquer tipo) pelo código.

**Resposta:**  `CMD,OK*` 

#### CMD,GEOCDELALL*
**Descrição:** Remove todas as geocercas circulares.

**Resposta:**  `CMD,OK*` 

#### CMD,GEORDELALL*
**Descrição:** Remove todas as geocercas retangulares.

**Resposta:**  `CMD,OK*` 

#### CMD,GEOPDELALL*
**Descrição:** Remove todas as geocercas poligonais.

**Resposta:**  `CMD,OK*` 

---

### 1.7 Comandos de Configuração Específica

#### CMD,CFG,DRIVER,<0|1>*
**Descrição:** Habilita/desabilita alarme de motorista não identificado.

**Parâmetros:**
- 0: Desabilitado
- 1: Habilitado

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,ENGCUT,<enabled>,<idle_time>,<min_time>*
**Descrição:** Configura o corte de motor ocioso.

**Parâmetros:**
- `enabled`: 0=Desabilitado, 1=Habilitado
- `idle_time`: Tempo de motor ocioso antes do corte (segundos)
- `min_time`: Tempo mínimo de corte (segundos)

**Resposta:**  `CMD,OK*` 

**Exemplo:**
```
CMD,CFG,ENGCUT,1,180,10*
```

#### CMD,CFG,RPM,<green_min>,<green_max>,<yellow_min>,<yellow_max>,<red_min>,<red_max>*
**Descrição:** Configura as zonas de RPM.

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,RPMDEF,<min>,<max>,<beep>,<enabled>*
**Descrição:** Configura RPM padrão com bip.

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,RPMLIM,<level1>,<level2>,<level3>*
**Descrição:** Configura limites de RPM.

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,TURBO,<max_pressure>*
**Descrição:** Configura pressão máxima do turbo.

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,TURBODEF,<default_value>*
**Descrição:** Configura valor padrão do turbo.

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,ENGTEMP,<max_temp>*
**Descrição:** Configura temperatura máxima do motor.

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,FUELOUT,<threshold>*
**Descrição:** Configura limiar de saída de combustível.

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,FUELIN,<threshold>*
**Descrição:** Configura limiar de entrada de combustível.

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,SPEED,<conversion_factor>*
**Descrição:** Configura fator de conversão de velocidade.

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,KEYBOARD,<modo>*
**Descrição:** Define o tipo de teclado conectado ao equipamento.

**Parâmetros:**
- `modo`: `0` = teclado com display LCD, `1` = modo apenas RFID (sem LCD).

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,UART,<porta>,<baud>,<bits>,<stop>,<flow>*
**Descrição:** Ajusta os parâmetros das interfaces seriais periféricas **internas** (não recomendado para uso em integração).

**Parâmetros:**
- `porta`: `2`=CAN, `3`=teclado/RFID, `5`=TPMS, `6`=sensor de inclinação.
- `baud`: baud rate em bps (por exemplo `115200`).
- `bits`: bits de dados (tipicamente `8`).
- `stop`: bits de parada (`1` ou `2`).
- `flow`: caractere de controle de fluxo (`N`=sem fluxo, `H`=hardware). Apenas o primeiro caractere é considerado.

**Resposta:**  `CMD,OK*`

**Nota:** Este comando afeta apenas as interfaces internas do dispositivo. A porta UART1 (interface principal) não pode ser reconfigurada por este comando. 

#### CMD,CFG,TXT,UART,<porta>,<dados>*
**Descrição:** Encaminha texto ASCII diretamente para uma UART periférica **interna** ou para a própria UART1.

**Parâmetros:**
- `porta`: `1` (envio bruto pela UART1), `2`=CAN, `3`=teclado, `5`=TPMS, `6`=sensor de inclinação.
- `dados`: texto ASCII sem o caractere final `*`. Para a porta 2 o firmware acrescenta `\r\n` automaticamente.

**Observações:**
- Porta `1`: o texto é transmitido exatamente como recebido pela UART1.
- Portas `2`, `3`, `5`, `6`: o texto é colocado na fila de transmissão do periférico correspondente.

**Resposta:**  `CMD,OK*`

**Nota:** Este comando é avançado e destinado a aplicações especiais. Para uso normal de integração, não é necessário. 

#### CMD,MP3,<codigo_hex>*
**Descrição:** Dispara a reprodução de um áudio pré-gravado no módulo MP3 interno.

**Parâmetros:** `codigo_hex` deve ser um valor hexadecimal de dois dígitos (`00` a `FF`).

**Resposta:**  `CMD,OK*` 

#### CMD,SMS,<mensagem>*
**Descrição:** Exibe uma mensagem no display do teclado (modo LCD).

**Comportamento:**
- Mensagem limitada a 32 caracteres; espaços duplicados são condensados e o caractere `*` é ignorado.
- Se o teclado estiver configurado como LCD (`CMD,CFG,KEYBOARD` = `0`), a primeira linha exibe até 16 caracteres e o restante segue para a segunda linha.
- Em modo RFID (`CMD,CFG,KEYBOARD` = `1`) o comando é ignorado após o `CMD,OK*`.

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,ROLL,<angle>*
**Descrição:** Configura ângulo de alarme de capotamento.

**Parâmetros:**
- `angle`: Ângulo em graus (0-90)

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,DHL,<enabled>,<rpm_max>,<speed_min>,<seconds_min>*
**Descrição:** Configura detecção de descida em ponto morto (downhill).

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,PULSE,<enabled>*
**Descrição:** Habilita/desabilita modo de pulso.

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,VEL,<faixa>,<vel_beep>,<vel_alarme>,<tempo>,<aciona_out2>*
**Descrição:** Configura uma faixa de velocidade para alertas automáticos.

**Parâmetros:**
- `faixa`: `1` ou `2`.
- `vel_beep`: velocidade (km/h) que ativa o aviso sonoro interno.
- `vel_alarme`: velocidade (km/h) que dispara os alarmes `ALM,101` (faixa 1) ou `ALM,102` (faixa 2).
- `tempo`: tempo mínimo em segundos acima de `vel_alarme` para gerar o alarme.
- `aciona_out2`: `0` ou `1` para acionar a saída OUT2 durante o alarme.

**Resposta:**  `CMD,OK*` 
#### CMD,CFG,IN,<port>,<level>,<enabled>,<notify_on>,<notify_off>,<beep>*
**Descrição:** Configura uma entrada digital (IN3-IN10).

**Parâmetros:**
- `port`: Número da porta (3-10)
- `level`: Nível lógico (0 ou 1)
- `enabled`: Entrada habilitada (0 ou 1)
- `notify_on`: Notificar quando ativada (0 ou 1)
- `notify_off`: Notificar quando desativada (0 ou 1)
- `beep`: Bip habilitado (0 ou 1)

**Resposta:**  `CMD,OK*` 

#### CMD,OUT,<port>,<state>*
**Descrição:** Controla uma saída digital (OUT2-OUT5).

**Parâmetros:**
- `port`: Número da saída (2-5)
- `state`: Estado (0=desligado, 1=ligado)

**Resposta:**  `CMD,OK*` 

**Exemplo:**
```
CMD,OUT,2,1*
```

#### CMD,CFG,RPM_CLR*
**Descrição:** Limpa contadores de RPM.

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,TURBO_CLR*
**Descrição:** Limpa contador de turbo.

**Resposta:**  `CMD,OK*` 

#### CMD,CFG,ENG_CLR*
**Descrição:** Limpa contadores do motor.

**Resposta:**  `CMD,OK*` 

#### ODO_CLR*
**Descrição:** Limpa odômetro.

**Resposta:**  `CMD,OK*` 

---

### 1.8 Comandos de Debug/Log

#### LOG_GPS*
**Descrição:** Ativa log da comunicação GPS.

**Resposta:**  `CMD,OK*` 

#### LOG_CAN*
**Descrição:** Ativa log da comunicação CAN.

**Resposta:**  `CMD,OK*` 

#### LOG_KEYBOARD*
**Descrição:** Ativa log da comunicação do teclado/RFID.

**Resposta:**  `CMD,OK*` 

#### LOG_TILT*
**Descrição:** Ativa log do sensor de inclinação.

**Resposta:**  `CMD,OK*` 

#### LOG_OFF*
**Descrição:** Desativa todos os logs.

**Resposta:**  `CMD,OK*` 

---

## 2. DADOS TRANSMITIDOS PELO DISPOSITIVO

Além das respostas aos comandos, o dispositivo envia automaticamente diversos tipos de informação via UART1.

### 2.1 Mensagem de Inicialização

**Formato:**
```
TOSERVER,STARTUP*
```

**Quando é enviada:** Ao iniciar o sistema após boot ou reset.

---

### 2.2 Dados de CAN Bus

O dispositivo transmite periodicamente (a cada 500ms) os dados lidos do barramento CAN do veículo.

**Formato:**
```
FR1,<estado_motor>,<odometro>,<hodometro>,<temperatura_oleo>,<nivel_combustivel>,<velocidade>,<rpm>,<pressao_freio>,<nivel_agua>,<temperatura_motor>,<pressao_oleo>,<nivel_ad_blue>,<nivel_diesel>,<pressao_turbo>,<nivel_ureia>,<gas_kickdown>,<contador_gas_kickdown>,<tensao_bateria>,<pressao_turbo_bar>,<velocidade_cruzeiro>,<temperatura_agua>,<nivel_diesel_2>,<rpm_verde_cntr>,<rpm_amarelo_cntr>,<rpm_vermelho_cntr>,<downhill_cntr>,<rpm_freq>,<velocidade_freq>,<odometro_absoluto>,<roll>,<pitch>,<temperatura_ambiente>,<alarme_capotamento>,<in3>,<in4>,<duracao_turbo>,<in5>,<in6>,<in7>,<in8>,<in9>,<in10>,<out2>,<out3>,<out4>,<out5>*
```

**Campos principais:**
- `estado_motor`: 0=Desligado, 1=Auxiliar, 2=Ligado
- `odometro`: Odômetro do veículo (km)
- `nivel_combustivel`: Nível de combustível (%)
- `velocidade`: Velocidade (km/h)
- `rpm`: Rotação do motor (RPM)
- `temperatura_motor`: Temperatura do motor (°C)
- `pressao_turbo`: Pressão do turbo (kPa)
- `rpm_verde_cntr`: Contador de tempo em zona verde de RPM
- `rpm_amarelo_cntr`: Contador de tempo em zona amarela de RPM
- `rpm_vermelho_cntr`: Contador de tempo em zona vermelha de RPM
- `downhill_cntr`: Contador de descida em ponto morto
- `roll`: Ângulo de rolagem (graus)
- `pitch`: Ângulo de pitch (graus)
- `alarme_capotamento`: 1=Alarme ativo, 0=Normal
- `in3-in10`: Estado das entradas digitais (0 ou 1)
- `out2-out5`: Estado das saídas digitais (0 ou 1)

**Exemplo:**
```
FR1,2,150000,2500,85,75,80,1800,400,90,88,250,85,80,150,75,0,0,13.8,1.5,0,88,80,12500,8500,3200,150,1800,80,150000,5,2,25,0,1,0,50,0,0,0,0,0,0,1,0,0*
```

**Mensagens CAN não-convencionais:**

O dispositivo também pode transmitir mensagens especiais do CAN com prefixo TOSERVER:

**Formato:**
```
TOSERVER,<mensagem_can>*
```

**Prefixos válidos:**
- `CAR`: Informações do veículo
- `LIMITS`: Limites configurados
- `REBOOT`: Comando de reboot
- `VERSION`: Versão
- `@MODE`: Modo de operação
- `CONFIG`: Configuração
- `DEBUG`: Debug
- `RAPIDS`: Rapids

**Exemplo:**
```
TOSERVER,CAR_MODEL_XYZ*
TOSERVER,VERSION_1.2.3*
```

---

### 2.3 Dados de TPMS (Sensores de Pressão dos Pneus)

Quando um sensor TPMS é detectado, o dispositivo envia os dados do sensor.

**Formato:**
```
TPMS,<id_sensor>|<alarme>|<pressao>|<temperatura>*
```

**Campos:**
- `id_sensor`: ID do sensor TPMS (12 caracteres hex)
- `alarme`: Código de alarme
  - 0: Normal
  - 1: Pressão fora dos limites
  - 2: Temperatura fora dos limites
  - 3: Pressão E temperatura fora dos limites
  - 4: Bateria baixa
  - 5: Bateria baixa + pressão fora dos limites
  - 6: Bateria baixa + temperatura fora dos limites
  - 7: Bateria baixa + pressão E temperatura fora dos limites
- `pressao`: Pressão medida (kPa, convertida com fator 0.74)
- `temperatura`: Temperatura medida (°C, offset -50)

**Exemplo:**
```
TPMS,1A2B3C4D5E6F|0|210|35*
TPMS,9F8E7D6C5B4A|1|150|40*
TPMS,5A6B7C8D9E0F|4|220|38*
```

---

### 2.4 Dados de Motorista e Atividade

Quando um motorista é identificado via teclado/RFID e um código de atividade é inserido:

**Formato:**
```
DRV,<id_motorista>,ACT,<codigo_atividade>*
```

**Campos:**
- `id_motorista`: ID do motorista (11 dígitos)
- `codigo_atividade`: Código da atividade (2 dígitos)

**Exemplo:**
```
DRV,12345678901,ACT,05*
```

---

### 2.5 Alarmes (ALM)

O dispositivo envia alarmes para diversas condições. Todos os alarmes seguem o formato:

**Formato Geral:**
```
ALM,<codigo>,<dados>*
```

#### Códigos de Alarme:

| Código | Descrição | Formato de Dados | Exemplo |
|--------|-----------|------------------|---------|
| 101 | Excesso de velocidade (faixa 1) | `<velocidade>` | `ALM,101,85*` |
| 102 | Excesso de velocidade (faixa 2) | `<velocidade>` | `ALM,102,105*` |
| 103 | Excesso de velocidade em geocerca | `<velocidade>` | `ALM,103,85*` |
| 104 | Entrada em geocerca | `<codigo_cerca>` | `ALM,104,C001*` |
| 105 | Saída de geocerca | `<codigo_cerca>` | `ALM,105,R002*` |
| 106 | Pressão de turbo acima do limite | `<pressao_turbo>` | `ALM,106,250*` |
| 107 | Descida em ponto morto (downhill) | `<contador>` | `ALM,107,150*` |
| 108 | Saída de combustível detectada | `<nivel_atual>` | `ALM,108,45*` |
| 109 | Entrada de combustível detectada | `<nivel_atual>` | `ALM,109,85*` |
| 110 | Inclinação lateral acima do limite | `<roll>` | `ALM,110,28*` |
| 111 | Temperatura do motor acima do limite | `<temperatura>` | `ALM,111,115*` |
| 112 | RPM acima do limite | `<rpm>` | `ALM,112,3800*` |
| 113 | Motorista não identificado | `<velocidade>` | `ALM,113,65*` |
| 114 | Corte de motor ocioso ativado | `1` | `ALM,114,1*` |
| 124 | Mudança de estado da entrada IN4 | `<estado>` | `ALM,124,1*` |
| 125 | Mudança de estado da entrada IN5 | `<estado>` | `ALM,125,0*` |
| 126 | Mudança de estado da entrada IN6 | `<estado>` | `ALM,126,1*` |
| 127 | Mudança de estado da entrada IN7 | `<estado>` | `ALM,127,1*` |
| 128 | Mudança de estado da entrada IN8 | `<estado>` | `ALM,128,0*` |
| 129 | Mudança de estado da entrada IN9 | `<estado>` | `ALM,129,1*` |
| 130 | Mudança de estado da entrada IN10 | `<estado>` | `ALM,130,1*` |
| 142 | Mudança de estado da saída OUT2 | `<estado>` | `ALM,142,1*` |
| 143 | Mudança de estado da saída OUT3 | `<estado>` | `ALM,143,0*` |
| 144 | Mudança de estado da saída OUT4 | `<estado>` | `ALM,144,1*` |
| 145 | Mudança de estado da saída OUT5 | `<estado>` | `ALM,145,0*` |

**Notas sobre Alarmes:**

1. **ALM,101/102** (Controle de velocidade configurável):
   - Disparados quando a velocidade permanece acima dos limites definidos em `CMD,CFG,VEL`.
   - Utilizam a velocidade do CAN ou do GPS conforme a configuração `CMD,CFG,SPEED`.

2. **ALM,103** (Excesso de velocidade em geocerca):
   - Enviado quando o veículo ultrapassa a velocidade máxima configurada para uma geocerca
   - Versões antigas enviavam também o código da cerca: `ALM,103,<velocidade>|<codigo>*`

3. **ALM,104/105** (Entrada/Saída de geocerca):
   - Depende da configuração `in_out` da geocerca
   - `in_out=1`: Alarme 104 na entrada
   - `in_out=0`: Alarme 105 na saída

4. **ALM,113** (Motorista não identificado):
   - Enviado quando o veículo está em movimento sem identificação de motorista

5. **ALM,110** (Inclinação lateral):
   - Enviado quando o valor absoluto de `roll` excede o limite configurado em `CMD,CFG,ROLL`.
### 2.6 Controle de Velocidade

O dispositivo monitora a velocidade e envia alarmes quando limites são ultrapassados:

**Formato:**
```
ALM,<codigo_alarme>,<velocidade>*
```

Os códigos de alarme de velocidade são definidos pelas faixas VEL1 e VEL2 configuradas.

---

### 2.7 Estados das Portas de Entrada/Saída

Mudanças nas entradas digitais (IN3-IN10) e saídas digitais (OUT2-OUT5) são reportadas via alarmes (veja seção 2.5).

---

## 3. NOTAS TÉCNICAS

### 3.1 Sistema de Dual-Slot (v1.2.8+)

A partir da versão 1.2.8, o dispositivo utiliza um sistema de backup rotativo com dois slots de configuração:
- **Slot 0**: Endereço 0x00000 (40KB)
- **Slot 1**: Endereço 0x0A000 (40KB)

**Características:**
- Cada salvamento grava no slot inativo, preservando backup
- Números de sequência identificam o slot mais recente
- Validação CRC32 detecta corrupção
- Boot inteligente seleciona o slot válido mais recente
- Fallback automático para slot anterior se corrupção detectada
- Comando `CMD,HEALTHGET*` reporta status de ambos os slots

### 3.2 Detecção de Tensão (PVD)

O monitor de tensão (PVD) previne operações de salvamento durante condições de tensão marginal:
- **SAFE**: Tensão normal, operações permitidas
- **WARNING**: Tensão baixa, salvamento bloqueado
- **CRITICAL**: Tensão crítica, sistema em modo protegido
- Tempo de estabilização: 2.5s após ignição desligada antes de salvar

### 3.3 Protocolo de Comunicação

- **Baudrate:** Varia por UART (consultar configuração do hardware)
- **Formato:** 8N1 (8 bits de dados, sem paridade, 1 stop bit)
- **Terminação:** Todos os comandos e respostas terminam com asterisco (*)
- **Timeout:** 15ms de idle timeout para detecção de fim de mensagem
- **Buffer RX:** Varia por módulo (150-512 bytes)

### 3.4 Arquitetura de Comunicação (UARTs)

**IMPORTANTE:** O dispositivo utiliza diferentes portas UART para diferentes funções:

| UART | Função | Direção | Conteúdo |
|------|--------|---------|----------|
| **UART1 (Principal)** | Interface de comunicação única | RX/TX | **RX:** Comandos (CMD,...) / **TX:** Respostas (CMD,OK / TOSERVER), dados automáticos (FR1, TPMS, DRV), alarmes (ALM) |
| **UART2 (CAN)** | Interface CAN bus | RX/TX | Comunicação com módulo CAN do veículo |
| **UART3 (Teclado)** | Teclado/RFID | RX | Identificação de motorista e código de atividade |
| **UART5 (TPMS)** | Sensores de pressão | RX | Dados dos sensores TPMS |
| **UART6 (Inclinação)** | Sensor de inclinação | RX | Dados do sensor tilt (roll/pitch) |

**Integração típica:**
- Conectar UART1 ao módulo GPS/Modem ou servidor para comunicação bidirecional
- Enviar comandos de configuração via UART1 (RX)
- Receber todos os dados (respostas, FR1, alarmes, TPMS, identificação) via UART1 (TX)
- UART1 é a **única interface externa** necessária para integração completa

### 3.5 Limites do Sistema

- **Motoristas:** Máximo 200 IDs
- **Códigos de Atividade:** Máximo 50
- **Sensores TPMS:** Máximo 60
- **Geocercas Circulares:** Máximo 30
- **Geocercas Retangulares:** Máximo 30
- **Geocercas Poligonais:** Máximo 30 (até 20 vértices cada)
- **Resposta DRVGET:** Máximo 80 motoristas por mensagem

### 3.6 Frequências de Transmissão

- **Dados CAN:** A cada 500ms (quando motor ligado)
- **Dados TPMS:** Quando sensor detectado (assíncrono)
- **Alarmes:** Imediato (event-driven)
- **Motorista/Atividade:** Quando identificação completa

---

## 4. FLUXO DE INTEGRAÇÃO TÍPICO

**IMPORTANTE:** Toda a comunicação (comandos, respostas, dados automáticos e alarmes) ocorre através da **UART1** de forma bidirecional. Esta é a única interface necessária para integração completa com o dispositivo.

### 4.1 Inicialização
1. Dispositivo envia `TOSERVER,STARTUP*` ao iniciar
2. Plataforma pode enviar `CMD,HEALTHGET*` para verificar status
3. Plataforma pode enviar `CMD,FWGET*` para verificar versão

### 4.2 Configuração Inicial
1. Enviar `CMD,CFGGET*` para obter configuração atual
2. Enviar comandos de configuração específicos conforme necessário
3. Cadastrar motoristas com `CMD,DRVADD,<id>*`
4. Cadastrar sensores TPMS com `CMD,TPMS,...*`
5. Configurar geocercas com `CMD,GEOC/GEOR/GEOP,...*`

### 4.3 Operação Normal
1. Receber dados CAN periodicamente (FR1,...)
2. Receber dados TPMS quando sensores transmitem
3. Receber identificações de motorista (DRV,...)
4. Processar alarmes (ALM,...)
5. Enviar comandos de controle conforme necessário

### 4.4 Manutenção
1. Usar `CMD,HEALTHGET*` para monitorar saúde do sistema
2. Usar `CMD,PVDGET*` para verificar condições de tensão
3. Backup periódico da configuração via `CMD,CFGGET*`

---

## 5. EXEMPLOS DE COMUNICAÇÃO

### Exemplo 1: Adicionar Motorista
```
→ CMD,DRVADD,12345678901*
← CMD,OK*
```

### Exemplo 2: Configurar Geocerca Circular
```
→ CMD,GEOC,C001,1,80,-23.5505,-46.6333,500*
← CMD,OK*
```

### Exemplo 3: Sequência de Identificação de Motorista
```
← DRV,12345678901,ACT,05*
```

### Exemplo 4: Alarme de Excesso de Velocidade
```
← ALM,103,95*
← ALM,104,C001*
```

### Exemplo 5: Dados CAN em Operação
```
← FR1,2,150000,2500,85,75,80,1800,400,90,88,250,85,80,150,75,0,0,13.8,1.5,0,88,80,12500,8500,3200,150,1800,80,150000,5,2,25,0,1,0,50,0,0,0,0,0,0,1,0,0*
```

### Exemplo 6: Verificação de Saúde do Sistema
```
→ CMD,HEALTHGET*
← TOSERVER,HEALTH,3600,25000,15000,40000,12,1,1,1,1,150,1,151,1*
```

---

## 6. TROUBLESHOOTING

### 6.1 Sem Resposta aos Comandos
- Verificar conexão física UART1
- Verificar terminação correta com asterisco (*)
- Verificar baudrate configurado
- Enviar `CMD,FWGET*` para teste básico

### 6.2 Dados CAN não Recebidos
- Verificar se motor está ligado (estado_motor=2)
- Verificar conexão do barramento CAN
- Validar formato da mensagem (22 vírgulas)

### 6.3 TPMS não Detectado
- Verificar se sensor está cadastrado com `CMD,TPMSGET*`
- Verificar RF do sensor TPMS
- Validar checksum dos dados recebidos

### 6.4 Alarmes não Enviados
- Verificar configurações com `CMD,CFGGET*`
- Verificar se condições de alarme estão sendo atingidas
- Para geocercas: verificar velocidade > 2 km/h

### 6.5 Perda de Configuração
- Sistema dual-slot (v1.2.8+) previne perda total
- Verificar status dos slots com `CMD,HEALTHGET*`
- Verificar tensão com `CMD,PVDGET*`
- Em caso de corrupção total: usar `CMD,MEM_CLR*` e reconfigurar

---

## 7. CHANGELOG DO PROTOCOLO

### v1.2.8 (128)
- Sistema dual-slot de backup rotativo
- Comando `CMD,HEALTHGET*` expandido com status de slots
- `CMD,MEM_CLR*` agora apaga ambos os slots

### v1.2.7 (127)
- Correção de duplicação de resposta GPS em UART1

### v1.2.6 (126)
- Implementação completa de geocercas poligonais
- Comandos `CMD,GEOPGET*`, `CMD,GEOP,...*`, `CMD,GEOPDELALL*`

### v1.2.5 (125)
- Comandos de exclusão em massa: `CMD,ACTDELALL*`, `CMD,GEOCDELALL*`, `CMD,GEORDELALL*`

### v1.2.4 (124)
- Comando `CMD,HEALTHGET*` para diagnóstico do sistema

### v1.2.1 (121)
- Monitor PVD de tensão
- Comando `CMD,PVDGET*`
- Proteção de salvamento em tensão marginal
- Delay de 2.5s após ignição desligada antes de salvar

### v1.2.0 (120)
- Corte de motor ocioso (alarme 114)
- Alarme de motorista não identificado (alarme 113)
- Comandos `CMD,CFG,ENGCUT*` e `CMD,CFG,DRIVER*`
- Permanência do leitor CAN independente de ignição
- Comandos multi-configuração `CMD,CFGGET*` e `CMD,CFGSET*`

---

## 8. CONTATO E SUPORTE

Para dúvidas sobre a integração ou suporte técnico, contactar a equipe de desenvolvimento SETERA.

**Versão do Documento:** 1.0
**Data:** Janeiro 2025
**Baseado em:** Firmware STR1010+ v1.2.8 (128)








