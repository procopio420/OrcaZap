"""Template rendering utilities."""

from typing import Optional
from uuid import UUID

from jinja2 import Environment, Template, select_autoescape
from sqlalchemy.orm import Session

from app.db.models import MessageTemplate
from app.domain.messages import format_quote_message, get_data_capture_prompt

# Create safe Jinja2 environment with autoescape enabled
_jinja_env = Environment(autoescape=select_autoescape(['html', 'xml']))


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
    template = _jinja_env.from_string(template_str)
    return template.render(**context)


def get_message_template(
    db: Session,
    tenant_id: UUID,
    template_type: str,
    name: Optional[str] = None,
) -> Optional[MessageTemplate]:
    """Get a message template from database.
    
    Args:
        db: Database session
        tenant_id: Tenant UUID
        template_type: Type of template ('data_capture', 'quote', 'approval', etc.)
        name: Optional template name (if None, gets the active default)
    
    Returns:
        MessageTemplate if found, None otherwise
    """
    query = db.query(MessageTemplate).filter_by(
        tenant_id=tenant_id,
        template_type=template_type,
        is_active=True,
    )
    
    if name:
        query = query.filter_by(name=name)
    else:
        # Get default (name is None or empty)
        query = query.filter((MessageTemplate.name == None) | (MessageTemplate.name == ""))
    
    return query.first()


def get_data_capture_template(
    db: Session,
    tenant_id: UUID,
    contact_name: Optional[str] = None,
) -> str:
    """Get data capture prompt, from DB template or default.
    
    Args:
        db: Database session
        tenant_id: Tenant UUID
        contact_name: Optional contact name for personalization
    
    Returns:
        Formatted message text
    """
    template = get_message_template(db, tenant_id, "data_capture")
    
    if template:
        # Render template with variables (safe with autoescape)
        jinja_template = _jinja_env.from_string(template.content)
        return jinja_template.render(contact_name=contact_name or "")
    
    # Fallback to default
    return get_data_capture_prompt(contact_name)


def get_quote_template(
    db: Session,
    tenant_id: UUID,
    quote_type: Optional[str] = None,
    **kwargs,
) -> str:
    """Get quote message template, from DB template or default.
    
    Args:
        db: Database session
        tenant_id: Tenant UUID
        quote_type: Optional quote type ('residencial', 'comercial', etc.)
        **kwargs: Template variables (items, subtotal, freight, etc.)
    
    Returns:
        Formatted message text
    """
    template = get_message_template(db, tenant_id, "quote", quote_type=quote_type)
    
    # Get tenant for signature
    from app.db.models import Tenant
    tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    tenant_name = tenant.name if tenant else ""
    
    if template:
        # Render template with variables (safe with autoescape)
        jinja_template = _jinja_env.from_string(template.content)
        rendered = jinja_template.render(
            tenant_name=tenant_name,
            **kwargs,
        )
        
        # Add signature if configured (safe with autoescape)
        if template.signature:
            signature_template = _jinja_env.from_string(template.signature)
            signature = signature_template.render(tenant_name=tenant_name)
            rendered += f"\n\n{signature}"
        
        return rendered
    
    # Fallback to default
    message = format_quote_message(
        items=kwargs.get("items", []),
        subtotal=kwargs.get("subtotal", 0.0),
        freight=kwargs.get("freight", 0.0),
        discount_pct=kwargs.get("discount_pct", 0.0),
        discount_amount=kwargs.get("discount_amount", 0.0),
        total=kwargs.get("total", 0.0),
        payment_method=kwargs.get("payment_method", ""),
        delivery_day=kwargs.get("delivery_day", ""),
        valid_until=kwargs.get("valid_until"),
    )
    
    # Add default signature if tenant name available
    if tenant_name:
        message += f"\n\nEquipe {tenant_name}"
    
    return message




