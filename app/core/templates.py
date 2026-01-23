"""Template rendering utilities."""

from jinja2 import Template


def render_template(template_name: str, context: dict) -> str:
    """Render a template from string templates.

    For MVP, we use simple string templates.
    In production, load from files using proper Jinja2 environment.
    """
    templates = {
        "public/landing.html": """
<!DOCTYPE html>
<html>
<head>
    <title>OrcaZap - Assistente de Orçamentos via WhatsApp</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }
        h1 { color: #007bff; }
        .warning { background: #fff3cd; border: 1px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 5px; }
        .warning strong { color: #856404; }
        .cta { display: inline-block; margin-top: 20px; padding: 12px 24px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>OrcaZap</h1>
    <h2>Assistente de Orçamentos via WhatsApp</h2>
    <p>Automatize o processo de orçamento para sua loja de material de construção via WhatsApp.</p>
    
    <h3>Como funciona:</h3>
    <ol>
        <li>Receba mensagens via WhatsApp</li>
        <li>Coleta de dados mínimos em um único bloco de perguntas</li>
        <li>Geração automática de orçamentos (regras de preço, frete, margens)</li>
        <li>Envio de orçamentos formatados via WhatsApp</li>
        <li>Aprovação humana para casos especiais (SKU desconhecido, margem baixa, etc.)</li>
    </ol>

    <div class="warning">
        <strong>⚠️ Aviso Importante:</strong>
        <p>Recomendamos fortemente o uso de um número de WhatsApp Business dedicado. 
        O uso de números pessoais pode resultar em bloqueios e limitações da plataforma WhatsApp.</p>
    </div>

    <a href="/register" class="cta">Começar Agora</a>
    <a href="/login" class="cta" style="background: #6c757d; margin-left: 10px;">Login</a>
</body>
</html>
""",
        "public/register.html": """
<!DOCTYPE html>
<html>
<head>
    <title>Registro - OrcaZap</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 500px; margin: 50px auto; padding: 20px; }
        form { display: flex; flex-direction: column; gap: 15px; }
        input { padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
        button { padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .error { color: red; margin-top: 10px; }
        a { color: #007bff; text-decoration: none; }
    </style>
</head>
<body>
    <h1>Registrar Nova Loja</h1>
    <form method="POST" action="/register">
        <input type="text" name="store_name" placeholder="Nome da Loja" required>
        <input type="email" name="email" placeholder="Email" required>
        <input type="password" name="password" placeholder="Senha" required minlength="8">
        <button type="submit">Registrar</button>
    </form>
    {% if error %}
    <p class="error">{{ error }}</p>
    {% endif %}
    <p><a href="/login">Já tem uma conta? Faça login</a></p>
</body>
</html>
""",
        "public/login.html": """
<!DOCTYPE html>
<html>
<head>
    <title>Login - OrcaZap</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 400px; margin: 50px auto; padding: 20px; }
        form { display: flex; flex-direction: column; gap: 15px; }
        input { padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
        button { padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .error { color: red; margin-top: 10px; }
        a { color: #007bff; text-decoration: none; }
    </style>
</head>
<body>
    <h1>Login</h1>
    <form method="POST" action="/login">
        <input type="email" name="email" placeholder="Email" required>
        <input type="password" name="password" placeholder="Senha" required>
        <button type="submit">Entrar</button>
    </form>
    {% if error %}
    <p class="error">{{ error }}</p>
    {% endif %}
    <p><a href="/register">Não tem uma conta? Registre-se</a></p>
</body>
</html>
""",
    }

    template_str = templates.get(template_name, "<p>Template not found: {{ template_name }}</p>")
    template = Template(template_str)
    return template.render(**context)


