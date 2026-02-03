"""Onboarding step templates."""

from jinja2 import Environment, select_autoescape

# Create safe Jinja2 environment with autoescape enabled
_jinja_env = Environment(autoescape=select_autoescape(['html', 'xml']))


def render_onboarding_step(step: int, context: dict) -> str:
    """Render onboarding step template."""
    templates = {
        1: """
<!DOCTYPE html>
<html>
<head>
    <title>Onboarding - Passo 1: Informações da Loja</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
        h1 { color: #007bff; }
        form { display: flex; flex-direction: column; gap: 15px; }
        input, textarea { padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
        button { padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .error { color: red; }
        .progress { margin: 20px 0; }
        .progress-bar { background: #e9ecef; height: 20px; border-radius: 10px; overflow: hidden; }
        .progress-fill { background: #007bff; height: 100%; width: 20%; }
    </style>
</head>
<body>
    <h1>Passo 1: Informações da Loja</h1>
    <div class="progress">
        <div class="progress-bar"><div class="progress-fill"></div></div>
        <p>Passo 1 de 5</p>
    </div>
    <form method="POST" action="/onboarding/step/1">
        <input type="text" name="store_name" placeholder="Nome da Loja" value="{{ store_name or '' }}" required>
        <input type="text" name="address" placeholder="Endereço" value="{{ address or '' }}">
        <input type="text" name="city" placeholder="Cidade" value="{{ city or '' }}">
        <input type="text" name="state" placeholder="Estado (UF)" value="{{ state or '' }}" maxlength="2">
        <input type="text" name="cep" placeholder="CEP" value="{{ cep or '' }}">
        <input type="text" name="phone" placeholder="Telefone de Contato" value="{{ phone or '' }}">
        <textarea name="notes" placeholder="Observações (opcional)">{{ notes or '' }}</textarea>
        <button type="submit">Continuar</button>
    </form>
    {% if error %}
    <p class="error">{{ error }}</p>
    {% endif %}
</body>
</html>
""",
        2: """
<!DOCTYPE html>
<html>
<head>
    <title>Onboarding - Passo 2: Regras de Frete</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 700px; margin: 50px auto; padding: 20px; }
        h1 { color: #007bff; }
        form { display: flex; flex-direction: column; gap: 15px; }
        .rule-group { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 4px; }
        input { padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        button { padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .add-rule { background: #28a745; margin-top: 10px; }
        .progress { margin: 20px 0; }
        .progress-bar { background: #e9ecef; height: 20px; border-radius: 10px; overflow: hidden; }
        .progress-fill { background: #007bff; height: 100%; width: 40%; }
    </style>
</head>
<body>
    <h1>Passo 2: Regras de Frete</h1>
    <div class="progress">
        <div class="progress-bar"><div class="progress-fill"></div></div>
        <p>Passo 2 de 5</p>
    </div>
    <p>Configure as regras de frete por bairro ou faixa de CEP.</p>
    <form method="POST" action="/onboarding/step/2">
        <div class="rule-group">
            <h3>Regra de Frete 1</h3>
            <input type="text" name="bairro_0" placeholder="Bairro (opcional)" value="">
            <input type="text" name="cep_start_0" placeholder="CEP Inicial (opcional)" value="">
            <input type="text" name="cep_end_0" placeholder="CEP Final (opcional)" value="">
            <input type="number" name="base_freight_0" placeholder="Frete Base (R$)" step="0.01" min="0" required>
            <input type="number" name="per_kg_0" placeholder="Por kg adicional (R$, opcional)" step="0.01" min="0">
        </div>
        <button type="button" class="add-rule" onclick="addRule()">+ Adicionar Regra</button>
        <button type="submit">Continuar</button>
    </form>
    <script>
        let ruleCount = 1;
        function addRule() {
            const form = document.querySelector('form');
            const ruleGroup = document.createElement('div');
            ruleGroup.className = 'rule-group';
            ruleGroup.innerHTML = `
                <h3>Regra de Frete ${ruleCount + 1}</h3>
                <input type="text" name="bairro_${ruleCount}" placeholder="Bairro (opcional)">
                <input type="text" name="cep_start_${ruleCount}" placeholder="CEP Inicial (opcional)">
                <input type="text" name="cep_end_${ruleCount}" placeholder="CEP Final (opcional)">
                <input type="number" name="base_freight_${ruleCount}" placeholder="Frete Base (R$)" step="0.01" min="0" required>
                <input type="number" name="per_kg_${ruleCount}" placeholder="Por kg adicional (R$, opcional)" step="0.01" min="0">
            `;
            form.insertBefore(ruleGroup, form.querySelector('.add-rule'));
            ruleCount++;
        }
    </script>
</body>
</html>
""",
        3: """
<!DOCTYPE html>
<html>
<head>
    <title>Onboarding - Passo 3: Regras de Preço</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
        h1 { color: #007bff; }
        form { display: flex; flex-direction: column; gap: 15px; }
        input { padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
        button { padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .progress { margin: 20px 0; }
        .progress-bar { background: #e9ecef; height: 20px; border-radius: 10px; overflow: hidden; }
        .progress-fill { background: #007bff; height: 100%; width: 60%; }
        .help-text { color: #6c757d; font-size: 0.9em; }
    </style>
</head>
<body>
    <h1>Passo 3: Regras de Preço</h1>
    <div class="progress">
        <div class="progress-bar"><div class="progress-fill"></div></div>
        <p>Passo 3 de 5</p>
    </div>
    <form method="POST" action="/onboarding/step/3">
        <label>
            Desconto PIX (%)
            <input type="number" name="pix_discount_pct" placeholder="0.05" step="0.0001" min="0" max="1" required>
            <span class="help-text">Ex: 0.05 para 5% de desconto</span>
        </label>
        <label>
            Margem Mínima (%)
            <input type="number" name="margin_min_pct" placeholder="0.10" step="0.0001" min="0" max="1" required>
            <span class="help-text">Margem mínima aceita antes de requerer aprovação</span>
        </label>
        <label>
            Limite Total para Aprovação (R$)
            <input type="number" name="approval_threshold_total" placeholder="1000.00" step="0.01" min="0">
            <span class="help-text">Orçamentos acima deste valor requerem aprovação (opcional)</span>
        </label>
        <label>
            Limite de Margem para Aprovação (%)
            <input type="number" name="approval_threshold_margin" placeholder="0.05" step="0.0001" min="0" max="1">
            <span class="help-text">Orçamentos abaixo desta margem requerem aprovação (opcional)</span>
        </label>
        <button type="submit">Continuar</button>
    </form>
</body>
</html>
""",
        4: """
<!DOCTYPE html>
<html>
<head>
    <title>Onboarding - Passo 4: Itens Principais</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 700px; margin: 50px auto; padding: 20px; }
        h1 { color: #007bff; }
        form { display: flex; flex-direction: column; gap: 15px; }
        textarea { padding: 10px; border: 1px solid #ddd; border-radius: 4px; min-height: 200px; }
        button { padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .progress { margin: 20px 0; }
        .progress-bar { background: #e9ecef; height: 20px; border-radius: 10px; overflow: hidden; }
        .progress-fill { background: #007bff; height: 100%; width: 80%; }
        .help-text { color: #6c757d; font-size: 0.9em; margin-top: 5px; }
        .example { background: #f8f9fa; padding: 10px; border-radius: 4px; margin: 10px 0; }
    </style>
</head>
<body>
    <h1>Passo 4: Itens Principais</h1>
    <div class="progress">
        <div class="progress-bar"><div class="progress-fill"></div></div>
        <p>Passo 4 de 5</p>
    </div>
    <p>Importe seus itens principais via CSV ou adicione manualmente.</p>
    <form method="POST" action="/onboarding/step/4" enctype="multipart/form-data">
        <label>
            Upload CSV (opcional)
            <input type="file" name="csv_file" accept=".csv">
            <span class="help-text">Formato: SKU,Nome,Unidade,Preço Base</span>
        </label>
        <div class="example">
            <strong>Exemplo CSV:</strong><br>
            ABC123,Cimento CP II-E-32,kg,25.50<br>
            XYZ789,Tijolo Cerâmico,un,0.85
        </div>
        <label>
            Ou adicione manualmente (um por linha):
            <textarea name="items_manual" placeholder="SKU,Nome,Unidade,Preço Base
ABC123,Cimento CP II-E-32,kg,25.50
XYZ789,Tijolo Cerâmico,un,0.85"></textarea>
        </label>
        <button type="submit">Continuar</button>
    </form>
    <p><small>Você pode adicionar mais itens depois no painel.</small></p>
</body>
</html>
""",
        5: """
<!DOCTYPE html>
<html>
<head>
    <title>Onboarding - Passo 5: Conectar WhatsApp</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 700px; margin: 50px auto; padding: 20px; }
        h1 { color: #007bff; }
        .warning { background: #fff3cd; border: 1px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 5px; }
        .warning strong { color: #856404; }
        .info { background: #d1ecf1; border: 1px solid #bee5eb; padding: 15px; margin: 20px 0; border-radius: 5px; }
        .progress { margin: 20px 0; }
        .progress-bar { background: #e9ecef; height: 20px; border-radius: 10px; overflow: hidden; }
        .progress-fill { background: #007bff; height: 100%; width: 100%; }
        ol { line-height: 1.8; }
        button { padding: 12px 24px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 1.1em; }
    </style>
</head>
<body>
    <h1>Passo 5: Conectar WhatsApp</h1>
    <div class="progress">
        <div class="progress-bar"><div class="progress-fill"></div></div>
        <p>Passo 5 de 5</p>
    </div>
    
    <div class="warning">
        <strong>⚠️ Aviso Importante sobre Números Pessoais:</strong>
        <p>Recomendamos fortemente o uso de um número de WhatsApp Business dedicado. 
        O uso de números pessoais pode resultar em:</p>
        <ul>
            <li>Bloqueios temporários ou permanentes da conta</li>
            <li>Limitações de funcionalidades da plataforma WhatsApp</li>
            <li>Risco de perda de acesso ao número</li>
        </ul>
        <p>Para uso comercial, utilize WhatsApp Business API ou um número dedicado.</p>
    </div>

    <div class="info">
        <h3>Como conectar seu WhatsApp:</h3>
        <ol>
            <li><strong>Crie uma conta no Meta for Developers</strong><br>
                Acesse <a href="https://developers.facebook.com" target="_blank">developers.facebook.com</a> e crie uma conta.</li>
            <li><strong>Crie um App e configure WhatsApp Business API</strong><br>
                Siga o guia oficial do Meta para configurar o WhatsApp Business API.</li>
            <li><strong>Obtenha suas credenciais</strong><br>
                Você precisará de:
                <ul>
                    <li>Phone Number ID</li>
                    <li>Business Account ID (WABA ID)</li>
                    <li>Access Token</li>
                    <li>Webhook Verify Token</li>
                </ul>
            </li>
            <li><strong>Configure o webhook</strong><br>
                Configure o webhook para: <code>https://api.orcazap.com/webhooks/whatsapp</code><br>
                Use o token de verificação que você configurou.</li>
        </ol>
    </div>

    <form method="POST" action="/onboarding/step/5">
        <p><strong>Você já configurou o WhatsApp Business API?</strong></p>
        <p>Se sim, você pode inserir as credenciais agora. Caso contrário, você pode fazer isso depois no painel.</p>
        <button type="submit">Finalizar Onboarding</button>
    </form>
</body>
</html>
""",
    }

    template_str = templates.get(step, "<p>Step not found</p>")
    template = _jinja_env.from_string(template_str)
    return template.render(**context)




