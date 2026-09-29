"""PaySage: an accounts-payable agent that learns from human decisions (memory: Hindsight).

    config.py    settings, read from .env
    models.py    every data shape: invoices, POs, exceptions, recommendations, API responses
    agent/       the decision pipeline: pipeline.py runs rules.py, Hindsight memory, llm.py and guardrail.py
    memory/      hindsight.py: retain, recall and reflect
    storage/     vendors, POs and the invoice queue; the decision log; MySQL
    utils/       logging (secrets redacted) and the command line's output
"""
