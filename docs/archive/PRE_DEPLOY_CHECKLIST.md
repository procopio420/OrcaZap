# Pré-Deploy Checklist

**Data**: 2024-12-19  
**Status**: Preparação para deploy de teste

---

## ✅ Verificações Antes do Deploy

### 1. Dependências
- [x] `requirements.txt` atualizado
- [x] Redis adicionado (já estava)
- [x] Todas as novas dependências incluídas

### 2. Migrations
- [x] Migration `007_add_missing_indexes.py` criada
- [ ] Migration testada localmente (se possível)
- [ ] Verificar ordem das migrations

### 3. Configurações
- [ ] Variáveis de ambiente configuradas no `.env` do servidor
- [ ] Redis URL configurada
- [ ] Database URL configurada
- [ ] WhatsApp tokens configurados (se aplicável)
- [ ] LLM API keys configuradas (se aplicável)

### 4. Código
- [x] Linter sem erros
- [x] Imports corretos
- [x] Todas as mudanças commitadas

---

## 🚀 Passos para Deploy

### 1. Preparar Ambiente Local
```bash
# Verificar que está no branch correto
git status
git branch

# Verificar migrations
ls -la alembic/versions/
```

### 2. Deploy App (VPS1)
```bash
cd infra/scripts/deploy

# Dry-run primeiro
./deploy_app.sh --host VPS1_HOST --dry-run

# Deploy real
./deploy_app.sh --host VPS1_HOST
```

### 3. Rodar Migrations
```bash
cd infra/scripts/deploy

# Rodar migrations
./migrate.sh --host VPS1_HOST
```

### 4. Deploy Worker (VPS3)
```bash
cd infra/scripts/deploy

# Deploy worker
./deploy_worker.sh --host VPS3_HOST
```

### 5. Verificar Health
```bash
# Verificar health check
curl https://api.orcazap.com/monitoring/health

# Verificar readiness
curl https://api.orcazap.com/monitoring/ready
```

---

## ⚠️ Pontos de Atenção

### Redis
- **IMPORTANTE**: Redis deve estar rodando e acessível
- Sessions agora dependem de Redis
- Se Redis estiver down, autenticação não funcionará

### Migrations
- Migration `007_add_missing_indexes.py` adiciona índices
- Pode demorar em tabelas grandes
- Fazer backup antes (se houver dados)

### Environment Variables
Novas variáveis que podem ser necessárias:
- `REDIS_URL` - Já estava, mas verificar
- `OPENAI_API_KEY` - Opcional (se usar LLM)
- `ANTHROPIC_API_KEY` - Opcional (se usar LLM)

### CSRF Tokens
- Cookies CSRF são setados no login
- HTMX precisa incluir `X-CSRF-Token` header
- Verificar se frontend está enviando token

---

## 🔍 Verificações Pós-Deploy

### 1. Logs
```bash
# Ver logs da aplicação
journalctl -u orcazap-app -f

# Ver logs do worker
journalctl -u orcazap-worker -f
```

### 2. Services
```bash
# Verificar status
systemctl status orcazap-app
systemctl status orcazap-worker

# Verificar se estão rodando
ps aux | grep uvicorn
ps aux | grep rq
```

### 3. Database
```bash
# Verificar conexão
psql $DATABASE_URL -c "SELECT 1"

# Verificar migrations aplicadas
psql $DATABASE_URL -c "SELECT version_num FROM alembic_version"
```

### 4. Redis
```bash
# Verificar conexão
redis-cli -u $REDIS_URL ping

# Verificar sessões (se houver)
redis-cli -u $REDIS_URL KEYS "session:*"
```

### 5. Endpoints
```bash
# Health check
curl https://api.orcazap.com/monitoring/health

# Metrics
curl https://api.orcazap.com/monitoring/metrics

# Ready check
curl https://api.orcazap.com/monitoring/ready
```

---

## 🐛 Troubleshooting

### Erro: "No module named 'app.core.sessions'"
**Causa**: Código não foi deployado ou venv não atualizado  
**Solução**: 
```bash
# Re-deploy
./deploy_app.sh --host VPS1_HOST
```

### Erro: "Redis connection failed"
**Causa**: Redis não está acessível  
**Solução**:
```bash
# Verificar Redis
redis-cli -u $REDIS_URL ping

# Verificar firewall/WireGuard
ping VPS2_WIREGUARD_IP
```

### Erro: "CSRF token missing"
**Causa**: Cookie CSRF não está sendo setado  
**Solução**: Verificar se login está funcionando e setando cookies

### Erro: "Migration already applied"
**Causa**: Migration já foi rodada  
**Solução**: Verificar estado atual:
```bash
alembic current
alembic history
```

---

## 📝 Notas

- **Primeiro deploy**: Pode precisar criar usuário `orcazap` e diretórios
- **Migrations**: Sempre fazer backup antes (se houver dados)
- **Redis**: Se não tiver Redis, sessions não funcionarão
- **HTTPS**: Em produção, cookies devem ter `secure=True`

---

**Última Atualização**: 2024-12-19





