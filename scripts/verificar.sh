#!/usr/bin/env bash
# Verificações do ambiente (cartão F01). Não altera nada: só lê e consulta.
#
#   scripts/verificar.sh env              confere o arquivo .env (antes de subir)
#   scripts/verificar.sh http [URL]       confere o site já no ar: página, health e WebSocket
#                                         URL padrão: http://localhost
#   scripts/verificar.sh                  roda "env" e depois "http"
#
# Para provar que a VM está acessível, rode o "http" de OUTRO computador, usando o
# endereço da VM (http://<endereço-da-vm>). Rodar na própria VM com localhost não prova isso.
# Precisa de: bash e curl. Sai com código 1 se qualquer verificação falhar.

set -u

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FALHAS=0

ok()    { printf '  [ok]    %s\n' "$1"; }
falha() { printf '  [FALHA] %s\n' "$1"; FALHAS=$((FALHAS + 1)); }
aviso() { printf '  [aviso] %s\n' "$1"; }

# Lê CHAVE=valor do .env sem executá-lo (o arquivo é só dados, nunca código).
valor_env() {
  grep -E "^$1=" "$RAIZ/.env" | tail -n 1 | cut -d= -f2- | tr -d '\r'
}

verificar_env() {
  echo "== .env =="
  local arq="$RAIZ/.env"
  if [ ! -f "$arq" ]; then
    falha ".env não existe. Rode: cp .env.example .env  (e troque a senha)"
    return
  fi
  ok ".env existe"

  if grep -q $'\r' "$arq"; then
    falha ".env tem quebras de linha do Windows (CRLF); converta para LF (o valor da senha ficaria com um \\r escondido)"
  fi

  local chave valor
  for chave in POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB; do
    valor="$(valor_env "$chave")"
    if [ -z "$valor" ]; then
      falha "$chave ausente ou vazia no .env"
    else
      ok "$chave definida"
    fi
  done

  # Toda variável ativa (não comentada) do .env.example precisa existir no .env. Cobre o caso
  # "puxei código novo que exige uma variável nova e esqueci de acrescentá-la no .env da VM".
  # (git pull nunca altera o .env.) Variável opcional fica comentada no .env.example.
  if [ -f "$RAIZ/.env.example" ]; then
    while IFS= read -r chave; do
      case "$chave" in POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_DB) continue ;; esac  # já checadas acima
      if grep -q "^${chave}=" "$arq"; then
        ok "$chave presente"
      else
        falha "$chave está no .env.example mas falta no .env (copie a linha e ajuste o valor)"
      fi
    done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$RAIZ/.env.example" | cut -d= -f1)
  fi

  valor="$(valor_env POSTGRES_PASSWORD)"
  if [ -n "$valor" ]; then
    if [[ "$valor" =~ [^A-Za-z0-9._~-] ]]; then
      falha "POSTGRES_PASSWORD tem caractere que quebra a URL de conexão; use só letras, números e - . _ ~ (ex.: openssl rand -hex 24)"
    fi
    if [ "$valor" = "troque-esta-senha" ]; then
      aviso "POSTGRES_PASSWORD ainda é a senha de exemplo; troque antes de publicar na VM (e antes de criar o banco: ver README)"
    fi
  fi

  # O .env não pode ir para o git (só dá para checar se isto for um repositório git).
  if command -v git >/dev/null 2>&1 && git -C "$RAIZ" rev-parse --git-dir >/dev/null 2>&1; then
    if git -C "$RAIZ" ls-files --error-unmatch .env >/dev/null 2>&1; then
      falha ".env está versionado no git! Remova do índice: git rm --cached .env"
    elif git -C "$RAIZ" check-ignore -q .env; then
      ok ".env está no .gitignore e fora do git"
    else
      falha ".env não está ignorado pelo git (verifique o .gitignore)"
    fi
  else
    aviso "não é um repositório git; checagem do .gitignore pulada"
  fi
}

verificar_http() {
  local base="${1:-http://localhost}"
  base="${base%/}"
  echo "== site em $base =="

  if ! command -v curl >/dev/null 2>&1; then
    falha "curl não encontrado"
    return
  fi

  local corpo codigo
  # 1) Página do React (Nginx servindo o frontend compilado)
  corpo="$(curl -sS --max-time 10 -w '\n%{http_code}' "$base/" 2>&1)"
  codigo="${corpo##*$'\n'}"
  if [ "$codigo" = "200" ] && grep -q 'id="root"' <<<"$corpo"; then
    ok "GET /  → 200 com a página do React"
  else
    falha "GET /  → esperado 200 com <div id=\"root\">; recebido: ${codigo:-sem resposta} (${corpo%%$'\n'*})"
  fi

  # 2) Rota do React sem arquivo correspondente cai no index.html (try_files)
  corpo="$(curl -sS --max-time 10 -w '\n%{http_code}' "$base/leiloes/1" 2>&1)"
  codigo="${corpo##*$'\n'}"
  if [ "$codigo" = "200" ] && grep -q 'id="root"' <<<"$corpo"; then
    ok "GET /leiloes/1  → 200 (rota do React resolvida pelo Nginx)"
  else
    falha "GET /leiloes/1  → esperado 200 com a página do React; recebido: ${codigo:-sem resposta}"
  fi

  # 3) Navegador → Nginx → API → banco
  corpo="$(curl -sS --max-time 10 -w '\n%{http_code}' "$base/api/health" 2>&1)"
  codigo="${corpo##*$'\n'}"
  if [ "$codigo" != "200" ]; then
    falha "GET /api/health  → esperado 200; recebido: ${codigo:-sem resposta} (${corpo%%$'\n'*})"
  elif grep -Eq '"db" *: *"ok"' <<<"$corpo"; then
    ok "GET /api/health  → 200 com \"db\": \"ok\" (Nginx → API → PostgreSQL)"
  else
    falha "GET /api/health  → API respondeu, mas o banco não está ok: ${corpo%%$'\n'*}"
  fi

  # 4) WebSocket pelo Nginx: o handshake precisa dar 101 e a chave de aceite correta.
  # A chave abaixo é o exemplo do RFC 6455; o aceite esperado para ela é conhecido.
  # O curl fica esperando mensagens depois do 101, então ele termina por tempo (--max-time) de propósito.
  local cab
  cab="$(curl -sS -i -N --http1.1 --max-time 4 \
      -H 'Connection: Upgrade' -H 'Upgrade: websocket' \
      -H 'Sec-WebSocket-Version: 13' -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
      "$base/api/ws" 2>/dev/null | tr -d '\r' | head -n 20)"
  if ! head -n 1 <<<"$cab" | grep -q ' 101'; then
    falha "WS /api/ws  → esperado 101 Switching Protocols; recebido: '$(head -n 1 <<<"$cab")'"
  elif grep -qi '^sec-websocket-accept: *s3pPLMBiTxaQ9kYGzzhZRbK+xOo=$' <<<"$cab"; then
    ok "WS /api/ws  → 101 com aceite correto (Nginx repassa o WebSocket)"
  else
    falha "WS /api/ws  → 101, mas sem o Sec-WebSocket-Accept esperado (algo no meio não é o servidor WebSocket)"
  fi
  echo "  (a troca de mensagens ao vivo se confere na página inicial: botão 'Enviar \"olá\"')"
}

modo="${1:-tudo}"
case "$modo" in
  env)  verificar_env ;;
  http) verificar_http "${2:-}" ;;
  tudo) verificar_env; verificar_http "${2:-}" ;;
  *)    echo "uso: $0 [env | http [URL]]" >&2; exit 2 ;;
esac

echo
if [ "$FALHAS" -eq 0 ]; then
  echo "Resultado: tudo certo."
else
  echo "Resultado: $FALHAS verificação(ões) falharam."
  exit 1
fi
