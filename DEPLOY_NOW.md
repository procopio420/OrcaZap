# Deploy Rápido - OrçaZap

**Data**: 2024-12-19  
**Status**: Pronto para deploy de teste

---

## ⚡ Quick Start

### 1. Verificar Mudanças
```bash
# Ver o que foi modificado
git status

# Ver resumo das mudanças principais
git diff --stat
```

### 2. Commit (se necessário)
```bash
# Se ainda não commitou as mudanças
git add .
git commit -m "feat: Add CSRF protection, Redis sessions, and security fixes"
```

### 3. Deploy App (VPS1)
```bash
cd infra/scripts/deploy

# Configurar variáveis (se ainda não configurou)
export SSH_PRIVATE_KEY="$(pwd)/../../deploy_key"
export INVENTORY_FILE="$(pwd)/../../inventory/hosts.env"

# Deploy
./deploy_app.sh --host VPS1_HOST
```

### 4. Rodar Migrations
```bash
cd infra/scripts/deploy

# Rodar migrations (inclui novo índice)
./migrate.sh --host VPS1_HOST
```

### 5. Deploy Worker (VPS3)
```bash
cd infra/scripts/deploy

# Deploy worker
./deploy_worker.sh --host VPS3_HOST
```

### 6. Verificar
```bash
# Health check
curl https://api.orcazap.com/monitoring/health

# Ready check (verifica DB)
curl https://api.orcazap.com/monitoring/ready
```

---

## 🔴 IMPORTANTE: Antes do Deploy

### Redis DEVE estar rodando
Sessions agora dependem de Redis. Se Redis estiver down:
- ❌ Login não funcionará
- ❌ Autenticação falhará
- ❌ CSRF tokens não serão validados

**Verificar Redis**:
```bash
# No VPS2 (DATA server)
redis-cli ping
# Deve retornar: PONG
```

### Migration Nova
A migration `007_add_missing_indexes.py` será aplicada. Ela:
- ✅ Adiciona índices (rápido, mesmo com dados)
- ✅ É reversível (tem downgrade)
- ⚠️ Pode demorar se tabela `quotes` for muito grande

---

## 📋 Checklist Rápido

- [ ] Redis está rodando no VPS2
- [ ] Database está acessível
- [ ] Variáveis de ambiente configuradas (`.env` no servidor)
- [ ] Código commitado (se usar git)
- [ ] Deploy app executado
- [ ] Migrations rodadas
- [ ] Deploy worker executado
- [ ] Health checks passando

---

## 🐛 Se Algo Der Errado

### Erro: "ModuleNotFoundError: No module named 'app.core.sessions'"
**Solução**: Re-deploy o app
```bash
./deploy_app.sh --host VPS1_HOST
```

### Erro: "Redis connection failed"
**Solução**: Verificar Redis
```bash
# No VPS2
systemctl status redis
redis-cli ping
```

### Erro: "CSRF token missing" no login
**Solução**: Verificar se cookies estão sendo setados. Pode ser problema de HTTPS/domínio.

### Erro: Migration falha
**Solução**: Verificar estado atual
```bash
# No VPS1
cd /opt/orcazap
sudo -u orcazap venv/bin/alembic current
sudo -u orcazap venv/bin/alembic history
```

---

## ✅ Verificações Pós-Deploy

### 1. Logs
```bash
# App
journalctl -u orcazap-app -n 50 --no-pager

# Worker  
journalctl -u orcazap-worker -n 50 --no-pager
```

### 2. Services
```bash
systemctl status orcazap-app
systemctl status orcazap-worker
```

### 3. Testar Login
1. Acessar `https://orcazap.com/login`
2. Fazer login
3. Verificar se cookies `session_id` e `csrf_token` são setados
4. Verificar se consegue acessar dashboard

### 4. Testar CSRF
1. Fazer login
2. Tentar salvar um template
3. Deve funcionar (token CSRF está sendo validado)

---

## 📝 Mudanças Principais no Deploy

### Novos Arquivos
- `app/core/csrf.py` - Proteção CSRF
- `app/core/sessions.py` - Sessions em Redis
- `app/core/retry.py` - Retry logic
- `app/core/template_validation.py` - Validação de templates
- `app/core/logging_config.py` - Logging estruturado
- `alembic/versions/007_add_missing_indexes.py` - Nova migration

### Arquivos Modificados
- `app/admin/auth.py` - Usa Redis para sessions
- `app/admin/routes.py` - CSRF protection
- `app/routers/tenant.py` - CSRF protection
- `app/routers/public.py` - CSRF + Redis sessions
- `app/core/templates.py` - Jinja2 autoescape
- `app/db/base.py` - Connection pooling
- `app/db/models.py` - Novos índices
- `app/main.py` - Structured logging
- `app/settings.py` - Novos timeouts

---

## 🚀 Próximos Passos Após Deploy

1. ✅ Testar login/logout
2. ✅ Testar criação de templates
3. ✅ Testar aprovação de orçamentos
4. ✅ Verificar logs para erros
5. ✅ Monitorar métricas no `/monitoring/metrics`

---

**Boa sorte com o deploy! 🎉**


