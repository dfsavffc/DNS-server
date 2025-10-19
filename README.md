# DNS Server (Python)

Авторитативный DNS-сервер на Python 3.12+.
Поддерживает запросы типов **A, AAAA, CNAME, TXT, NS, PTR** и **ANY**.
Источником записей служит YAML-файл `config.yaml`. Сервер отвечает только за то, что описано в конфигурации (AA=1, RA=0).

---

## Требования

- **Python 3.12+**
- dnslib
- PyYAML

---

## Установка и сборка

```bash
git clone https://github.com/dfsavffc/DNS-server
cd src/dns_server

python3 -m venv .venv
# Windows: ..venvScriptsactivate
# Linux/macOS:
source .venv/bin/activate

pip install -e .
```

## Конфигурация (`config.yaml`)

Пример:

```yaml
default_ttl: 300
records:
  - name: example.com.
    type: A
    value: 203.0.113.10

  - name: example.com.
    type: AAAA
    value: 2001:db8::10

  - name: www.example.com.
    type: CNAME
    value: example.com.

  - name: example.com.
    type: NS
    value: ns1.example.com.

  - name: example.com.
    type: TXT
    value: "v=spf1 -all"

  - name: 10.113.0.203.in-addr.arpa.
    type: PTR
    value: example.com.
```

Правила:

- Все имена — **FQDN** с **точкой в конце** (например, `example.com.`).
- Для `CNAME` / `NS` / `PTR` значение — тоже FQDN с точкой.

---

## Запуск

### Вариант для разработки (нестандартный порт)

```bash
dns-server --config config.yaml --host 127.0.0.1 --port 5300 --log-level DEBUG
```

### Порт 53

Потребуются права администратора/root и свободный порт:

```bash
dns-server --config config.yaml --host 0.0.0.0 --port 53
```

---

## Проверка

### `nslookup`

```bash
nslookup -type=A -port=5300 example.com. 127.0.0.1
nslookup -type=AAAA -port=5300 example.com. 127.0.0.1
nslookup -type=CNAME -port=5300 www.example.com. 127.0.0.1
nslookup -type=TXT -port=5300 example.com. 127.0.0.1
```

### `dig`

```bash
dig @127.0.0.1 -p 5300 example.com. A
dig @127.0.0.1 -p 5300 example.com. ANY
```

Ожидаемое:

- `status: NOERROR` для существующих записей
- Флаг `aa`=1, `ra`=0
- Значения совпадают с `config.yaml`
- Для `CNAME` в **additional** могут приходить A/AAAA цели (best-effort)

---

## Структура проекта

```
dns-server/
├─ pyproject.toml
├─ README.md
├─ config.yaml
├─ .gitignore
└─ src/
   └─ dns_server/
      ├─ __init__.py
      ├─ __main__.py
      ├─ cli.py
      ├─ config.py
      ├─ records.py
      ├─ protocol.py
      └─ server.py
```
