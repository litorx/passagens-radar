# ✈️ Passagens Radar — SP → América do Sul, 24 h, grátis, controlado pelo celular

Varre preços de **GRU/CGH/VCP** para ~20 destinos da América do Sul **da data de hoje até onde as companhias vendem**
(hoje ≈ outubro/2027; o radar descobre o limite sozinho e te avisa quando novas datas abrem), aprende o que é
"normal" para cada destino e mês, e **te avisa no Telegram quando algo cai muito abaixo do normal**.
Você muda tudo pelo celular, mandando comandos para o seu bot.

## Como é montado (e por quê)

| Parte | Onde roda | O que faz |
|---|---|---|
| **Radar de dinheiro** (`scan.yml`) | GitHub Actions (grátis, 24 h) | Google Flights, grade de datas rotativa, detector de fora da curva, aviso |
| **Bot** (`bot.yml`) | GitHub Actions, a cada ~5 min | Lê seus comandos do Telegram e altera a config |
| **Radar de milhas** (`scan_miles`) | **Seu PC** (Agendador do Windows) | Smiles (e LATAM Pass, experimental): milhas e milhas+dinheiro |

**Por que milhas rodam no seu PC:** testado em 02/11/2026: a API da Smiles responde bloqueio (HTTP 406) até do IP residencial;
funciona com **Chrome real + Playwright em janela visível** (modo invisível é bloqueado), e um projeto aberto
(`GAHLicita/Buscador-de-passagens`) documenta que a Smiles bloqueia os servidores do GitHub. Por isso a janela abre
**fora da tela** (-32000) e o PC precisa estar ligado e logado. A LATAM exige login: você entra uma vez num perfil local.

## Instalação (já feita para o bot @PassagensPintinhobot; refaça só se quiser um novo)
1. **Telegram:** @BotFather → `/newbot` → token.  2. **GitHub:** `gh repo create passagens-radar --public --source . --push`
   e `gh secret set TELEGRAM_BOT_TOKEN`.  3. Mande `/start` ao bot; descubra seu chat id (o bot responde em até 5 min,
   ou abra `https://api.telegram.org/bot<TOKEN>/getUpdates`) e `gh secret set TELEGRAM_CHAT_ID --body <id>`.
4. **PC (milhas):** crie `data_local/.env` com `TELEGRAM_BOT_TOKEN=...`, `TELEGRAM_CHAT_ID=...`,
   `CONFIG_URL=https://raw.githubusercontent.com/<usuario>/passagens-radar/main/data/config.json`; depois
   `pip install -r requirements-local.txt` e `.\windows\instalar_tarefa.ps1`. LATAM (opcional): `python -m radar.sources.latam --login`.
> **Repositório público** de propósito (Actions ilimitado e grátis). Ficam visíveis só rotas e preços; token e chat id ficam em
> *Secrets* / `data_local/.env` (ignorado pelo git). **Se o token vazar, gere outro no @BotFather (`/revoke`) e troque o Secret.**

## Mudar o destino para qualquer continente (pelo celular)
`/regioes` lista: `brasil`, `america_do_sul`, `america_central`, `america_norte`, `europa`, `asia`, `africa`, `oceania`, `mundo`.
- `/regiao europa` troca TODOS os destinos por Europa · `/regiao europa asia` combina · `/regiao+ africa` acrescenta.
- `/add JFK` ou `/remover LIS` ajustam aeroporto a aeroporto. Origem é sempre **SP (GRU, CGH, VCP)**; mude com `/origens`.
- Regiões grandes demoram mais para dar a volta: use `/passo 5` e `/duracoes 7` para varrer mais rápido.

## Escala oculta (voos com conexão para lugares mais longe)
O radar também compara, para cada **hub** configurado, o preço **só ida até um destino mais longe com conexão no hub** contra
o preço de **ir só até o hub**. Se for ≥ 20 % mais barato, avisa com 🔴. **Zona cinza:** é "hidden city": viola o contrato da
companhia (só bagagem de mão, só ida, não use conta de milhas; o resto do bilhete pode ser cancelado).
`/escala on|off` · `/escala+ SCL SYD AKL` (hub e destinos além) · `/escala- SCL` · `/economiaescala 20`.
(Voos com conexão até o PRÓPRIO destino já entram na busca normal: o preço é o menor entre todas as opções.)

## Comandos do celular
`/ajuda` lista todos. Os principais:
`/status` · `/agora` · `/pausar` · `/retomar` · `/add SCL LIM` · `/remover SCL` · `/origens GRU CGH VCP` ·
`/intervalo 2` · `/silencio 23 7` (ou `off`) · `/sensibilidade 30` · `/limite SCL 1100` · `/ate 2027-12-31` ·
`/duracoes 5 7 10` · `/passo 3` · `/milhas on` · `/milheiro 16` · `/limitemilhas SCL 90000` · `/ultimos`.

## Como decide "fora da curva"
1. Para cada **destino × mês de ida** guarda o histórico (até 120 dias).
2. Avisa se o preço está **≥ `/sensibilidade` % abaixo da mediana** *e* é um desvio forte (z robusto ≥ 2, mediana/MAD),
   com pelo menos 6 leituras. Já na 1ª rodada a própria grade de datas serve de comparação (ex.: Lima 21→28/nov custava
   33 % menos que o dia seguinte).
3. Ou se bater o seu **limite fixo** (`/limite`).
4. Não repete o mesmo aviso, a não ser que caia mais 5 %. Avisos no horário de silêncio ficam guardados e saem depois.
5. **Milhas:** soma ida+volta; compara com a mediana de milhas e mostra o **valor da milha** (R$/milheiro) contra o dinheiro
   mediano, para você ver se "milhas valem mais que dinheiro" naquela data (use `/milheiro` com o seu custo real).

## Limites honestos (testados)
- **Fonte de dinheiro = Google Flights via biblioteca não oficial** (`fast-flights`): **não lista low-cost** (Sky, JetSMART,
  Flybondi) e o preço pode diferir do site. Por isso todo aviso traz link do **Skyscanner** para conferir. Pode quebrar se o
  Google mudar; nesse caso o radar te avisa ("fonte falhando").
- **Janela até dez/2027:** as companhias só vendem ~11 meses à frente (testado: set/2027 tem preço; out–dez/2027 não).
- **Relógio do GitHub** é aproximado (atrasa alguns minutos) e o bot responde em até ~5 min, não na hora.
- Se o repositório ficar **60 dias sem atividade**, o GitHub pode desligar os agendamentos: abra a aba *Actions* e reative.
- **Milhas** usam o mesmo endpoint do site da Smiles; podem quebrar a qualquer mudança; use baixa frequência e respeite os termos.
  A LATAM Pass está **experimental** (extração validada ao vivo; loop automático com perfil persistente ainda não exercitado).
- Preços são **ida e volta, só bagagem de mão**. Sempre confirme o total no site da companhia antes de comprar.

## Estrutura
```
radar/            código (config, dates, outlier, store, notify, bot, poll, scan_cash, scan_miles, sources/)
data/config.json  sua configuração (editada pelo bot)      data/state.json  histórico (nuvem)
tests/            python -m unittest tests.test_radar
.github/workflows scan.yml (dinheiro) · bot.yml (comandos)  windows/  agendador das milhas
```
