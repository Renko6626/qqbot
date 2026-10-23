#!/usr/bin/env bash
# Build and inspect only this bot. Coolify retains control of deployment.
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINER="nonebot-8hzqwaltqvmjo73d5lkv2rll"
PYTHON_IMAGE="${QQBOT_PYTHON_IMAGE:-qqbot-python:3.13-20261023}"
COOLIFY_URL="https://coolify.secret-sealing.club/project/zedd9kjkwxycw6qtsf43f8gv/environment/zi47jjycv0tz997e8bvzzzrg/service/8hzqwaltqvmjo73d5lkv2rll"

usage() {
  cat <<'EOF'
Usage: bash ops/nonebot.sh COMMAND [IMAGE]

  update          git pull --ff-only, build, then point qqbot:manual at the result
  build           build this checkout, then point qqbot:manual at the result
  promote IMAGE   point qqbot:manual at an existing image (for rollback)
  status          show current container health and source revision
  logs            follow this container's last 100 log lines
  backup          archive only /data/qq-bot/nonebot into a root-private backup

Build/promote does not restart anything. Click Restart in the NoneBot Coolify
resource when ready. Password changes also require that Coolify Restart.
EOF
}

ready_to_publish() {
  printf 'Prepared image: %s\n' "$1"
  printf 'Next: click Restart on the NoneBot resource:\n%s\n' "$COOLIFY_URL"
  printf 'NapCat is not part of this operation.\n'
}

build() {
  local revision image
  revision="$(git -C "$PROJECT_ROOT" rev-parse --verify HEAD)"
  if [[ -n "$(git -C "$PROJECT_ROOT" status --porcelain --untracked-files=normal)" ]]; then
    printf 'Checkout has local changes. Commit or discard them before a versioned build.\n' >&2
    exit 1
  fi
  image="qqbot:git-${revision}"
  if ! docker image inspect "$PYTHON_IMAGE" >/dev/null 2>&1; then
    printf 'Missing base image %s. See docs/nonebot-operations.md.\n' "$PYTHON_IMAGE" >&2
    exit 1
  fi
  docker build --pull=false --build-arg "PYTHON_IMAGE=$PYTHON_IMAGE" \
    --label "org.opencontainers.image.revision=$revision" \
    --tag "$image" "$PROJECT_ROOT"
  docker tag "$image" qqbot:manual
  ready_to_publish "$image"
}

case "${1:-help}" in
  help|--help|-h) usage ;;
  update)
    git -C "$PROJECT_ROOT" pull --ff-only
    build
    ;;
  build) build ;;
  promote)
    [[ $# -eq 2 ]] || { usage >&2; exit 2; }
    docker image inspect "$2" >/dev/null
    docker tag "$2" qqbot:manual
    ready_to_publish "$2"
    ;;
  status)
    docker inspect "$CONTAINER" --format \
      'State={{.State.Status}} Health={{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}} Image={{.Config.Image}} ImageID={{.Image}} Started={{.State.StartedAt}}'
    docker inspect "$CONTAINER" --format \
      'Source revision={{index .Config.Labels "org.opencontainers.image.revision"}}'
    ;;
  logs) docker logs --tail 100 --follow "$CONTAINER" ;;
  backup)
    umask 077
    backup_dir="/root/qq-bot-nonebot/backups"
    mkdir -p "$backup_dir"
    archive="$backup_dir/nonebot-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
    tar -C /data/qq-bot -czf "$archive" nonebot
    printf 'Saved plugin configuration backup: %s\n' "$archive"
    ;;
  *) usage >&2; exit 2 ;;
esac
