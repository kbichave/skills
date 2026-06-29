def create_refund(payment_id: str) -> dict:
    return {"paymentId": payment_id, "status": "refunded"}
