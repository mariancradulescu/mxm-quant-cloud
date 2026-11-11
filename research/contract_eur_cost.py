"""EUR cost attribution from authenticated cTrader symbol contract and synchronized FX rates.

Research-only: CURRENT contract terms, not a historical tariff/fill assertion.
Physical units, lot cent scaling, quote/fee asset and rate provenance are explicit.
Historical BID/ASK spread is booked exactly once, or zero additional spread if
actual simulated entry/exit prices already contain the executable side.
"""
from decimal import Decimal as D

class IncompleteCostEvidence(ValueError):
    pass

def dec(v):
    if v is None:
        raise IncompleteCostEvidence("MISSING_NUMERIC_EVIDENCE")
    x=D(str(v))
    if not x.is_finite():
        raise IncompleteCostEvidence("INVALID_FINITE_NUMBER")
    return x

def _field(symbol, name):
    if not symbol.HasField(name):
        raise IncompleteCostEvidence("MISSING_CONTRACT_FIELD_"+name)
    return dec(getattr(symbol,name))

def fee_at_current_contract(symbol, quote_asset, units, price, asset_eur):
    """One-side contractual commission in EUR at a supplied observed price/rate.

    asset_eur maps an asset to POSITIVE *payable* EUR per asset at one causal
    clock (not a future/midpoint estimate). The caller must certify rate times.
    No assumption of zero when rate, min commission, currency or route is absent.
    """
    units=dec(units);price=dec(price)
    minimum=_field(symbol,"minVolume")/100
    step=_field(symbol,"stepVolume")/100
    maximum=_field(symbol,"maxVolume")/100
    lot=_field(symbol,"lotSize")/100
    if min(units,price,lot,minimum,step)<=0 or maximum<minimum:
        raise IncompleteCostEvidence("INVALID_VOLUME_OR_PRICE")
    if units<minimum or units>maximum or (units-minimum)%step!=0:
        raise IncompleteCostEvidence("VOLUME_NOT_ON_BROKER_GRID")
    if int(symbol.tradingMode)!=0:
        raise IncompleteCostEvidence("CONTRACT_NOT_OPEN_ENABLED")
    rate=_field(symbol,"preciseTradingCommissionRate")
    floor=_field(symbol,"preciseMinCommission")
    if rate<0 or floor<0:
        raise IncompleteCostEvidence("NEGATIVE_COMMISSION_WIRE")
    rates={k:dec(v) for k,v in asset_eur.items()}
    if any(x<=0 for x in rates.values()):
        raise IncompleteCostEvidence("NONPOSITIVE_EUR_RATE")
    def eur(amount,asset):
        if amount == 0:
            return D(0)
        if asset not in rates:
            raise IncompleteCostEvidence("MISSING_EUR_ROUTE_"+asset)
        return amount*rates[asset]
    typ=int(symbol.commissionType)
    if typ==1:  # USD per million USD notional
        # The same USD conversion cancels on the way into and out of USD.
        # Matches NativeBrokerContractCosts.CommissionPerUnit.
        base_eur=eur((rate/D(10)**8)/D(10)**6*units*price,quote_asset)
    elif typ==2:  # USD per lot
        base_eur=eur((rate/D(10)**8)*units/lot,"USD")
    elif typ==3:  # % of notional (rate multiplier 1e5, then /100)
        base_eur=eur((rate/D(10)**5)/100*units*price,quote_asset)
    elif typ==4:  # QUOTE currency per lot (never USD-per-lot)
        base_eur=eur((rate/D(10)**8)*units/lot,quote_asset)
    else:
        raise IncompleteCostEvidence("UNKNOWN_COMMISSION_TYPE")
    mintyp=int(symbol.minCommissionType)
    if mintyp==1:
        floor_asset=symbol.minCommissionAsset
        if not floor_asset:
            raise IncompleteCostEvidence("MINIMUM_FEE_ASSET_UNKNOWN")
    elif mintyp==2:
        floor_asset=quote_asset
    else:
        raise IncompleteCostEvidence("UNKNOWN_MINIMUM_COMMISSION_TYPE")
    floor_eur=eur(floor/D(10)**8,floor_asset)
    return {
      "oneSideContractCommissionEur":str(max(base_eur,floor_eur)),
      "baseCommissionEur":str(base_eur),
      "minimumCommissionEur":str(floor_eur),
      "minimumCommissionAsset":floor_asset,
      "commissionType":typ,
      "rateWireExplicit":symbol.HasField("preciseTradingCommissionRate"),
      "floorWireExplicit":symbol.HasField("preciseMinCommission"),
      "typeWireExplicit":symbol.HasField("commissionType"),
      "currentContractOnly":True,
      "historicalBrokerTariffCertified":False
    }

def attribute_costs(symbol, quote_asset, units, bid, ask, asset_eur,
                    execution_bid_ask_already_priced=False,
                    slippage_eur=None, financing_eur=None, gross_realized_eur=None):
    """Research cost envelope, never a funded net ledger.

    No rounded bps proxy and no duplicated spread. PnL conversion fee applies
    to a known positive realized GROSS only; unknown PnL keeps it unknown.
    Financing and slippage remain unknown if not supplied.
    """
    bid=dec(bid);ask=dec(ask);units=dec(units)
    if bid<=0 or ask<=bid:
        raise IncompleteCostEvidence("INVALID_BID_ASK")
    qrate=dec(asset_eur.get(quote_asset))
    if qrate<=0:
        raise IncompleteCostEvidence("INVALID_QUOTE_EUR_RATE")
    commission=fee_at_current_contract(symbol,quote_asset,units,ask,asset_eur)
    spread=(ask-bid)*units*qrate
    fixed_commission=2*dec(commission["oneSideContractCommissionEur"])
    added_spread=D(0) if execution_bid_ask_already_priced else spread
    pnl_conversion=None
    if quote_asset=="EUR":
        pnl_conversion=D(0)
    elif symbol.HasField("pnlConversionFeeRate") and gross_realized_eur is not None:
        gross=dec(gross_realized_eur)
        pnl_conversion=abs(gross)*dec(symbol.pnlConversionFeeRate)/10000
    elif gross_realized_eur is not None:
        raise IncompleteCostEvidence("PNL_CONVERSION_RATE_UNKNOWN")
    slip=None if slippage_eur is None else dec(slippage_eur)
    carry=None if financing_eur is None else dec(financing_eur)
    if slip is not None and slip<0 or carry is not None and carry<0:
        raise IncompleteCostEvidence("NEGATIVE_COST")
    known_floor=added_spread+fixed_commission
    total=(known_floor+slip+carry+pnl_conversion
           if slip is not None and carry is not None and pnl_conversion is not None else None)
    return {
      "spreadObservedEur":str(spread),
      "additionalSpreadBookedEur":str(added_spread),
      "modelPriceAlreadyIncludesBidAsk":bool(execution_bid_ask_already_priced),
      "roundTripCurrentContractCommissionEur":str(fixed_commission),
      "historicalTermsCertified":False,
      "pnlConversionFeeEur":None if pnl_conversion is None else str(pnl_conversion),
      "slippageEstimatedEur":None if slip is None else str(slip),
      "financingCostEur":None if carry is None else str(carry),
      "knownComponentsSubtotalEur":str(known_floor),
      "completeConditionalCostEur":None if total is None else str(total),
      "fundedBrokerNetEur":None,
      "fullHistoryCostCertified":False,
      "feeProvenance":commission
    }
