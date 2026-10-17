"""Deterministic agent application fixture; no model, network or dynamic execution."""
DOCUMENTS = {"handover": "Read durable project files before acting.", "review": "Major changes require independent evidence-bound review."}
def answer(query, role="reader", tool=None):
    if not isinstance(query, str) or not query.strip() or len(query) > 512:
        raise ValueError("Invalid query")
    if tool is not None:
        if tool != "read_status" or role != "reader":
            raise PermissionError("Tool request outside the declared read boundary")
        return {"status": "ready", "mutated": False}
    matches = [text for key, text in DOCUMENTS.items() if key in query.casefold()]
    return {"answer": " ".join(matches) if matches else "No supported local answer", "sources": [key for key in DOCUMENTS if key in query.casefold()]}
