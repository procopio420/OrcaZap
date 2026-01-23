"""Message templates and formatting."""

from datetime import datetime
from typing import Any


def get_data_capture_prompt(contact_name: str | None = None) -> str:
    """Get the data capture prompt message in PT-BR.

    Args:
        contact_name: Optional contact name for personalization

    Returns:
        Formatted message text
    """
    greeting = f"Olá{', ' + contact_name if contact_name else ''}! 👋"
    
    message = f"""{greeting}

Para gerar seu orçamento, preciso das seguintes informações:

📍 *Localização:* [CEP ou bairro]
💳 *Forma de pagamento:* [PIX / Cartão / Boleto]
📅 *Dia de entrega:* [Data ou "o quanto antes"]
📦 *Itens:* [Lista de produtos com quantidades]

Exemplo:
📍 CEP: 01310-100 ou Bairro: Centro
💳 PIX
📅 Amanhã
📦
- Cimento 50kg: 10 sacos
- Areia média: 2m³
- Tijolo comum: 500 unidades"""

    return message


def format_quote_message(
    items: list[dict[str, Any]],
    subtotal: float,
    freight: float,
    discount_pct: float,
    discount_amount: float,
    total: float,
    payment_method: str,
    delivery_day: str,
    valid_until: datetime,
) -> str:
    """Format quote message in PT-BR.

    Args:
        items: List of items with name, quantity, unit, total
        subtotal: Subtotal before discounts
        freight: Freight cost
        discount_pct: Discount percentage (0-1)
        discount_amount: Discount amount
        total: Total amount
        payment_method: Payment method
        delivery_day: Delivery day description
        valid_until: Quote expiration datetime

    Returns:
        Formatted message text
    """
    # Format items list
    items_text = "\n".join(
        f"• {item['name']} ({item['quantity']} {item['unit']}): R$ {item['total']:,.2f}".replace(",", ".")
        for item in items
    )

    # Format discount line (only if discount > 0)
    discount_text = ""
    if discount_pct > 0:
        discount_name = "PIX" if payment_method.upper() == "PIX" else "Desconto"
        discount_text = f"*Desconto {discount_name} ({discount_pct*100:.0f}%):* -R$ {discount_amount:,.2f}\n".replace(",", ".")

    # Format valid_until
    valid_until_str = valid_until.strftime("%d/%m/%Y às %H:%M")

    message = f"""✅ *Orçamento Gerado*

*Itens:*
{items_text}

*Subtotal:* R$ {subtotal:,.2f}
*Frete:* R$ {freight:,.2f}
{discount_text}━━━━━━━━━━━━━━━━
*Total:* R$ {total:,.2f}

💳 *Forma de pagamento:* {payment_method}
📅 *Entrega:* {delivery_day}

⏰ *Válido até:* {valid_until_str}

Para agendar a entrega, responda:
✅ *Confirmar* ou *Sim*

Ou envie sua dúvida que te ajudo! 😊"""

    return message.replace(",", ".")

