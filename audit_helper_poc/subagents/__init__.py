# audit_helper_poc/subagents/__init__.py
"""Subagent 注册模块"""
from .default_subagent import DefaultSubagent
from .rent_contract_subagent import RentContractSubagent
from .vat_tax_subagent import VatTaxSubagent
from .income_tax_subagent import IncomeTaxSubagent
from .financial_report_subagent import FinancialReportSubagent
from .tianyancha_subagent import TianyanchaSubagent
from .bank_confirmation_subagent import BankConfirmationSubagent
from .bank_detail_subagent import BankDetailSubagent
from .bank_balance_subagent import BankBalanceSubagent

__all__ = [
    "DefaultSubagent",
    "RentContractSubagent",
    "VatTaxSubagent",
    "IncomeTaxSubagent",
    "FinancialReportSubagent",
    "TianyanchaSubagent",
    "BankConfirmationSubagent",
    "BankDetailSubagent",
    "BankBalanceSubagent",
]