# ✈️ Passagens Radar — SP → mundo, 24 h, grátis, controlado pelo Telegram

Varre os **menores valores** saindo de São Paulo (GRU, CGH, VCP) para a região que você escolher, dentro do **período
que você definir**, e te avisa no Telegram quando algo está **fora da curva**. Tudo se muda pelo celular.

## Como funciona
| Parte | Onde | O que faz |
|---|---|---|
| **Radar** (`scan.yml`) | GitHub Actions (grátis, 24 h) | Busca no **Kiwi.com** (servidor MCP oficial: sem captcha, inclui low-cost como Sky/JetSMART), compara com o "normal" e avisa |
| **Bot** (`bot.yml`) | GitHub Actions, a cada ~5 min | Lê seus comandos e muda a configuração |
| **Milhas** (`scan_miles`, opcional) | **Seu PC** (Agendador do Windows) | Smiles e LATAM Pass (milhas e milhas+dinheiro); a Smiles bloqueia a nuvem |

**Por que Kiwi e não Skyscanner/Google:** testado em 03/11/2026: o Skyscanner passa a mostrar captcha ("você é um robô?") para
automação (e este projeto **não contorna captcha**); o Google via biblioteca não vê low-cost e traz preço mais alto. O Kiwi tem
API oficial para agentes, aceita **intervalo de datas de ida e volta**, devolve os mais baratos e achou o mesmo voo da Sky Airline
que o Skyscanner mostra.

## Período (o que você pediu)
- `/periodo 31/12/2026 05/01/2027` → **janela curta**: testa **todas** as combinações de ida e volta dentro dela.
- `/periodo dez/2026 dez/2027` → **janela longa**: busca os menores valores em qualquer data do intervalo, com viagens de
  `/duracoes` dias (padrão 5 a 10; `/duracoes 3-12` muda).
- `/periodo hoje dez/2027` → de hoje até o fim de 2027 (as companhias vendem ~11 meses; o que ainda não abriu não aparece).
- Formatos aceitos: `31/12/2026`, `2026-12-31`, `dez/2026`, `12/2026`, `hoje`.
- `/top` mostra **os menores valores agora** (todos os destinos); `/top 20` mostra mais.

## Destino em qualquer continente
`/regioes` · `/regiao europa` (troca) · `/regiao europa asia` (combina) · `/regiao+ africa` (acrescenta) · `/add JFK` · `/remover LIS`.
Regiões: brasil, america_do_sul, america_central, america_norte, europa, asia, africa, oceania, mundo. Origem: sempre SP.

## Comandos úteis
`/status` · `/agora` · `/pausar` · `/retomar` · `/intervalo 2` · `/silencio 23 7` (ou `off`) · `/sensibilidade 30` ·
`/limite SCL 1100` · `/bagagem despachada` · `/autotransferencia on|off` · `/escala on|off` · `/milhas on` · `/ajuda`.

## Como decide "fora da curva"
Para cada destino pega o menor valor do período e compara com (1) uma amostra de **meses do próprio período** e (2) o **histórico**
dele (mediana + MAD). Avisa se estiver ≥ `/sensibilidade` % abaixo do normal, ou abaixo do seu `/limite`. Não repete o mesmo aviso
(só se cair mais 5 %). Avisos no horário de silêncio saem depois.

## Escala oculta (zona cinza, ligada por padrão, `/escala off` desliga)
Compara a passagem **só ida** até um destino **mais longe com conexão num hub** (ex.: SP→Miami via Panamá) com a passagem só até o
hub. Só avisa se a rota realmente passa pelo hub. É "hidden city": viola o contrato da companhia (só bagagem de mão, só ida, sem
conta de milhas; o resto do bilhete pode ser cancelado).

## Instalação (já feita para @PassagensPintinhobot)
1. @BotFather → `/newbot` → token. 2. `gh repo create passagens-radar --public --source . --push` e `gh secret set TELEGRAM_BOT_TOKEN`.
3. Mande `/start`, pegue o chat id (`getUpdates`) e `gh secret set TELEGRAM_CHAT_ID --body <id>`.
4. Milhas no PC (opcional): `data_local/.env` com `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`; `pip install -r requirements-local.txt`;
`.\windows\instalar_tarefa.ps1`. Repositório **público** de propósito (Actions ilimitado e grátis); token só em Secrets/`.env` ignorado.
**Se o token vazar:** `/revoke` no @BotFather e troque o Secret.

## Limites honestos
- Preço é do **Kiwi.com**; pode diferir alguns % do Skyscanner. O link do aviso leva ao Kiwi para você ver o total (bagagem etc.).
- Por padrão o preço é **só item pessoal** (`/bagagem despachada` já inclui 1 mala). Companhias low-cost cobram mala à parte.
- `autotransferencia` desligada (bilhete único). Ligar baixa o preço mas, se o 1º voo atrasar, a 2ª companhia não te realoca.
- O relógio do GitHub atrasa alguns minutos; o bot responde em até ~5 min. Repositório 60 dias parado pode ter agendamentos
  desligados (abra a aba *Actions*).
- Milhas: endpoints não oficiais da Smiles/LATAM, podem quebrar; só no seu PC ligado e logado; LATAM é experimental.
- Sempre confirme o total no site antes de comprar.

## Estrutura
`radar/` (scan, kiwi, bot, poll, outlier, store, config, miles) · `data/config.json` (sua config) · `data/state.json`, `data/top.json`
· `tests/` (`python -m unittest tests.test_radar`) · `.github/workflows/` · `windows/`
