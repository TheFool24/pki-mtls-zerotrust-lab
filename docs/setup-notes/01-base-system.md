# 01 — Base system setup

**Дата:** 2026-05-19
**Хост:** master-lab (HP Z2 Tower G9)
**ОС:** Ubuntu Server 24.04 LTS (kernel 6.17.0-1020-oem)

## Изпълнени стъпки

### SSH key-based auth
- Генериран ed25519 ключ на личния PC (`jojo-thesis-lab-2026`)
- Публичният ключ копиран в `~/.ssh/authorized_keys` на контролера
- Допълнителен ключ от лаптопа добавен (TODO — потвърди дали си го добавил)
- SSH hardening приложен чрез drop-in `/etc/ssh/sshd_config.d/10-thesis-lab-hardening.conf`:
  - `PasswordAuthentication no`
  - `PubkeyAuthentication yes`
  - `PermitRootLogin no`
- Backup на оригиналния sshd_config: `/etc/ssh/sshd_config.bak-20260519`
- SSH config jump host pattern за бъдещи Pi nodes (на Windows PC-то)

### Sudoers
- `jojo` получи NOPASSWD sudo чрез `/etc/sudoers.d/90-jojo-nopasswd`
  - Решение за lab convenience (изпълнение на автоматизирани setup задачи)
  - **TODO — преди защитата**: revisit и евентуално премахни за по-production-like posture

### System hardening и base packages
- `apt update && upgrade` — пълно обновяване на пакетите
- Инсталирани: ca-certificates, curl, gnupg, lsb-release, git, vim, htop, tree, jq,
  chrony, unattended-upgrades, apt-listchanges, fail2ban, ufw, net-tools, tcpdump,
  iputils-ping, dnsutils, rsync, zip, unzip
- Hostname: `master-lab`
- Timezone: `Europe/Sofia`
- Locale generated: en_US.UTF-8, bg_BG.UTF-8

### NTP синхронизация
- chrony конфигуриран чрез drop-in `/etc/chrony/conf.d/thesis-lab.conf`
  - Primary: MikroTik `10.50.20.1` (с `prefer`)
  - Fallback (temporary, dev mode): `pool 2.bg.pool.ntp.org iburst`
- Ubuntu default pool-ове изключени в `/etc/chrony/chrony.conf`
- Verify: `chronyc sources` показва `^*` срещу `_gateway` (10.50.20.1)
- **TODO — преди защитата**: премахни public NTP pool за air-gap режим (изискване ОИ-5)

### Unattended security upgrades
- `unattended-upgrades` enabled чрез `/etc/apt/apt.conf.d/20auto-upgrades`
- `apt-daily.timer` и `apt-daily-upgrade.timer` enabled
- Auto reboot за kernel updates: disabled (preferring manual control)

### fail2ban
- SSH jail активиран чрез `/etc/fail2ban/jail.d/sshd.local`
- maxretry=3, findtime=600, bantime=3600
- На Ubuntu 24.04 fail2ban ползва systemd journal backend (не /var/log/auth.log директно)

### Docker Engine + Compose
- Официално Docker APT repo добавено (`/etc/apt/sources.list.d/docker.list`)
- GPG ключ: `/etc/apt/keyrings/docker.asc`
- Инсталирани (от Docker official repo):
  - `docker-ce` 29.5.1
  - `docker-ce-cli` 29.5.1
  - `containerd.io` 2.2.3
  - `docker-buildx-plugin` v0.34.0
  - `docker-compose-plugin` v5.1.3
- `jojo` добавен в `docker` group
- Storage driver: overlayfs (containerd snapshotter)
- Cgroup driver: systemd, Cgroup v2
- Smoke tests: `docker run --rm hello-world` ✓, `docker run --rm alpine + curl ifconfig.me` ✓
- Auto-start при boot: enabled (`docker.service` + `containerd.service`)

## Verify команди (snapshot)

```bash
# SSH
sudo systemctl status ssh
sudo sshd -T | grep -E "^(passwordauthentication|pubkeyauthentication|permitrootlogin) "

# NTP
chronyc sources
chronyc tracking
timedatectl status

# fail2ban
sudo fail2ban-client status sshd

# Docker
docker version
docker compose version
docker info | head -25
```

## Бележки за Глава 3

- Системните hardening мерки (fail2ban, key-only SSH, unattended security
  updates) са допълнителни layer-и към основната Zero Trust архитектура,
  не я заместват. Те защитават host операционната система.
- NTP синхронизацията към MikroTik (не към публични интернет сървъри) подготвя
  системата за air-gap режим по време на защитата (изискване ОИ-5). Текущият
  fallback към `2.bg.pool.ntp.org` е dev mode placeholder и ще бъде премахнат.
- Версията на Docker (29.x) и Compose plugin (v5.x) са по-нови от първоначално
  цитираните в Гл. 2.6 (28.x / v2). Текстът там ще се обнови в следваща редакция.
