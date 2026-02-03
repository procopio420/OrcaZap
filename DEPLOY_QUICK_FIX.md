# Quick Fix - Inventory File Path

O problema é que o script procura `infra/inventory/hosts.env` com caminho relativo.

## Solução Rápida

Execute o deploy da **raiz do projeto**:

```bash
# Da raiz do projeto (/home/lucas/hobby/orcazap)
cd /home/lucas/hobby/orcazap

# Ou se já estiver na raiz:
cd infra/scripts/deploy
./deploy_app.sh --host VPS1_HOST
```

## Solução Alternativa (se ainda não funcionar)

Defina a variável de ambiente:

```bash
export INVENTORY_FILE="$(pwd)/infra/inventory/hosts.env"
cd infra/scripts/deploy
./deploy_app.sh --host VPS1_HOST
```

## Verificação

O arquivo existe:
```bash
ls -la infra/inventory/hosts.env
# Deve mostrar o arquivo
```

---

**Nota**: Corrigi a função `load_inventory()` para encontrar o arquivo automaticamente, mas é mais seguro executar da raiz do projeto.


