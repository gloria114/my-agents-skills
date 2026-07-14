"""Human-reviewable pure-Python formulas for all locked WH6 outputs.

The 97 functions below use native Python arithmetic/comparison operators,
explicit topologically ordered local variables, and audited WH6 primitives.
There is no formula parsing or formula-file I/O at runtime.
"""

from __future__ import annotations

from typing import Any

from wh6_primitives import FormulaContext

SOURCE_FORMULA_MAP_SHA256 = 'd88c186c50dde492898468edd38ee07d6063a8f01be770f488e28f7d8a5f7689'
FORMULA_SOURCE_FORMAT = 'native-python-v2'

COLUMN_ORDER = (
    'wh6_ADTM_ADTM',
    'wh6_ADTM_ADTMMA',
    'wh6_ARBR_AR',
    'wh6_ARBR_BR',
    'wh6_ASI_ASI',
    'wh6_ATR_TR',
    'wh6_ATR_ATR',
    'wh6_B3612_B36',
    'wh6_B3612_B612',
    'wh6_BIAS_BIAS1',
    'wh6_BIAS_BIAS2',
    'wh6_BIAS_BIAS3',
    'wh6_CCI_CCI',
    'wh6_CR_CR',
    'wh6_CR_CRMA1',
    'wh6_CR_CRMA2',
    'wh6_CR_CRMA3',
    'wh6_CR_CRMA4',
    'wh6_DBCD_DBCD',
    'wh6_DBCD_MM',
    'wh6_DDI_DDI',
    'wh6_DDI_ADDI',
    'wh6_DDI_AD',
    'wh6_DMA_DDD',
    'wh6_DMA_AMA',
    'wh6_DMI_PDI',
    'wh6_DMI_MDI',
    'wh6_DMI_ADX',
    'wh6_DMI_ADXR',
    'wh6_DPO_DPO',
    'wh6_KD_K',
    'wh6_KD_D',
    'wh6_KDJ_K',
    'wh6_KDJ_D',
    'wh6_KDJ_J',
    'wh6_LON_LON',
    'wh6_LON_LONGMA',
    'wh6_LON_LONGT',
    'wh6_MACD_DIFF',
    'wh6_MACD_DEA',
    'wh6_MACD_MACD',
    'wh6_MASS_MASS',
    'wh6_MFI_MFI',
    'wh6_MI_A',
    'wh6_MI_MI',
    'wh6_MICD_DIF',
    'wh6_MICD_MICD',
    'wh6_MTM_MTM',
    'wh6_MTM_MTMMA',
    'wh6_PRICEOSC_PRICEOSC',
    'wh6_PSY_PSY',
    'wh6_PSY_PSYMA',
    'wh6_QHLSR_QHL5',
    'wh6_QHLSR_QHL10',
    'wh6_RC_ARC',
    'wh6_RCCD_DIF',
    'wh6_RCCD_RCCD',
    'wh6_ROC_ROC',
    'wh6_ROC_ROCMA',
    'wh6_RSI_RSI1',
    'wh6_RSI_RSI2',
    'wh6_SHORT_SHORT',
    'wh6_SHORT_SHORTMA',
    'wh6_SHORT_SHORTT',
    'wh6_SLOWKD_K',
    'wh6_SLOWKD_D',
    'wh6_SRDM_SRDM',
    'wh6_SRDM_ASRDM',
    'wh6_SRMI_SRMI',
    'wh6_STOCHASTIC_RSI_RSI_BASE',
    'wh6_STOCHASTIC_RSI_STOCH_RSI_RAW',
    'wh6_WR_WR',
    'wh6_ZDZB_B',
    'wh6_ZDZB_D',
    'wh6_ZLJC_JCS',
    'wh6_ZLJC_JCM',
    'wh6_ZLJC_JCL',
    'wh6_ZLMM_MMS',
    'wh6_ZLMM_MMM',
    'wh6_ZLMM_MML',
    'wh6_AD_AD',
    'wh6_CCL_CCL',
    'wh6_CJL_CJL',
    'wh6_MV_MV',
    'wh6_MV_MV_2',
    'wh6_MV_MV_3',
    'wh6_OBV_OBV',
    'wh6_OBV_OBVMA',
    'wh6_PVT_PVT',
    'wh6_VOSC_VOSC',
    'wh6_VOSC_OBVMA',
    'wh6_VR_VR',
    'wh6_VROC_VROC',
    'wh6_VRSI_VRSI',
    'wh6_WAD_WAD',
    'wh6_WVAD_WVAD',
    'wh6_u_78c25b4e_u_273a581d',
    'wh6_u_78c25b4e_u_2da16149',
    'wh6_u_78c25b4e_DT1',
    'wh6_u_78c25b4e_KT1',
    'wh6_BAR_BAR',
    'wh6_CLOSE_CLOSE',
    'wh6_DEMA_DEMA',
    'wh6_EMA_MA1',
    'wh6_EMA2_MA1',
    'wh6_HIGH_HIGH',
    'wh6_LOW_LOW',
    'wh6_MYFORCAST_MYFORCAST',
    'wh6_OPEN_OPEN',
    'wh6_SMA_SMA',
    'wh6_VOLATILITY_u_c40446c0',
    'wh6_u_d6d18ecd_u_d6d18ecd',
    'wh6_u_d6d18ecd_MA1',
    'wh6_BBI_BBI',
    'wh6_BBIBOLL_BBIBOLL',
    'wh6_BBIBOLL_UPR',
    'wh6_BBIBOLL_DWN',
    'wh6_BOLL_MID',
    'wh6_BOLL_TOP',
    'wh6_BOLL_BOTTOM',
    'wh6_CDP_CDP',
    'wh6_CDP_AH',
    'wh6_CDP_AL',
    'wh6_CDP_NH',
    'wh6_CDP_NL',
    'wh6_DKX_B',
    'wh6_DKX_D',
    'wh6_ENV_UPPER',
    'wh6_ENV_LOWER',
    'wh6_HCL_MAH',
    'wh6_HCL_MAL',
    'wh6_HCL_MAC',
    'wh6_MA_MA1',
    'wh6_MIKE_WR',
    'wh6_MIKE_MR',
    'wh6_MIKE_SR',
    'wh6_MIKE_WS',
    'wh6_MIKE_MS',
    'wh6_MIKE_SS',
    'wh6_PUBU_PB1',
    'wh6_PUBU_PB2',
    'wh6_PUBU_PB3',
    'wh6_PUBU_PB4',
    'wh6_PUBU_PB5',
    'wh6_PUBU_PB6',
    'wh6_SAR_SARLINE',
    'wh6_SAR1_SARLINE',
    'wh6_SP_SP',
    'wh6_WTD_WTD',
    'wh6_u_6ae5cc5a_HH',
    'wh6_u_6ae5cc5a_LL',
    'wh6_u_72bedb5a_MA15',
    'wh6_u_72bedb5a_MA30',
    'wh6_u_68173cb3_H20',
    'wh6_u_68173cb3_L20',
    'wh6_u_5c41ea6d_MA5',
    'wh6_u_5c41ea6d_MA10',
    'wh6_u_5c41ea6d_MA30',
    'wh6_u_21e0022b_MA1',
    'wh6_u_9a0c2be9_MA5',
    'wh6_u_9a0c2be9_MA10',
    'wh6_u_9a0c2be9_MA30',
    'wh6_u_6f963dfa_MA5',
    'wh6_u_6f963dfa_MA10',
    'wh6_FIBONACCI_BANDS_FIBONACCI_BANDS',
    'wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_2',
    'wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_3',
    'wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_4',
    'wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_5',
    'wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_6',
    'wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_7',
    'wh6_ROC_ROC_2',
    'wh6_ROC_ROCMA_2',
    'wh6_ROC_ROC_B',
    'wh6_RSIS_RSIS1',
    'wh6_RSIS_RSIS2',
    'wh6_RSI_WILDER_RSI1',
    'wh6_RSI_WILDER_RSI2',
    'wh6_VWMA_VWMA3',
    'wh6_Z_SCORE_Z_SCORE',
    'wh6_u_a8b37c90_MULTI',
    'wh6_u_a8b37c90_u_a8b37c90',
    'wh6_u_a8b37c90_u_a8b37c90_2',
    'wh6_u_a8b37c90_u_a8b37c90_3',
    'wh6_u_8b96f436_BBW',
    'wh6_u_dc9bfffe_UO',
    'wh6_u_495a23e5_MID',
    'wh6_u_495a23e5_UPPER',
    'wh6_u_495a23e5_LOWER',
    'wh6_u_dcb52af4_MID',
    'wh6_u_dcb52af4_TR',
    'wh6_u_dcb52af4_AAA',
    'wh6_u_dcb52af4_UPPER',
    'wh6_u_dcb52af4_LOWER',
    'wh6_MFI_MFI_2',
    'wh6_u_a4f8ae15_UPPER',
    'wh6_u_a4f8ae15_LOWER',
    'wh6_u_a4f8ae15_MIDDLE',
)

def formula_000_ADTM(ctx: FormulaContext) -> dict[str, Any]:
    """ADTM[6afdf7a14e11]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    OPEN = ctx.OPEN
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    IFELSE = ctx.IFELSE
    REF = ctx.REF
    MAX = ctx.MAX
    SUM = ctx.SUM
    MA = ctx.MA
    # Locked parameter defaults.
    N = 23.0  # N
    M = 8.0  # M

    # DTM
    DTM = (
        IFELSE((OPEN <= REF(OPEN, 1.0)), 0.0, MAX((HIGH - OPEN), (OPEN - REF(OPEN, 1.0))))
    )

    # STM
    STM = (
        SUM(DTM, N)
    )

    # DBM
    DBM = (
        IFELSE((OPEN >= REF(OPEN, 1.0)), 0.0, MAX((OPEN - LOW), (REF(OPEN, 1.0) - OPEN)))
    )

    # SBM
    SBM = (
        SUM(DBM, N)
    )

    # ADTM
    ADTM = (
        IFELSE((STM > SBM), ((STM - SBM) / STM), IFELSE((STM == SBM), 0.0, ((STM - SBM) / SBM)))
    )

    # ADTMMA
    ADTMMA = (
        MA(ADTM, M)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_ADTM_ADTM
    outputs['wh6_ADTM_ADTM'] = (
        ADTM
    )
    # Explicit locked output: wh6_ADTM_ADTMMA
    outputs['wh6_ADTM_ADTMMA'] = (
        ADTMMA
    )
    return outputs


def formula_001_AD(ctx: FormulaContext) -> dict[str, Any]:
    """AD[1c547921b117]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    LOW = ctx.LOW
    HIGH = ctx.HIGH
    VOL = ctx.VOL
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    SUM = ctx.SUM

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_AD_AD
    outputs['wh6_AD_AD'] = (
        SUM(((((CLOSE - LOW) - (HIGH - CLOSE)) / (HIGH - LOW)) * VOL), 0.0)
    )
    return outputs


def formula_002_ARBR(ctx: FormulaContext) -> dict[str, Any]:
    """ARBR[6b716a7bb085]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    HIGH = ctx.HIGH
    OPEN = ctx.OPEN
    LOW = ctx.LOW
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    SUM = ctx.SUM
    MAX = ctx.MAX
    REF = ctx.REF
    # Locked parameter defaults.
    N = 26.0  # N

    # AR
    AR = (
        ((SUM((HIGH - OPEN), N) / SUM((OPEN - LOW), N)) * 100.0)
    )

    # BR
    BR = (
        ((SUM(MAX(0.0, (HIGH - REF(CLOSE, 1.0))), N) / SUM(MAX(0.0, (REF(CLOSE, 1.0) - LOW)), N)) * 100.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_ARBR_AR
    outputs['wh6_ARBR_AR'] = (
        AR
    )
    # Explicit locked output: wh6_ARBR_BR
    outputs['wh6_ARBR_BR'] = (
        BR
    )
    return outputs


def formula_003_ASI(ctx: FormulaContext) -> dict[str, Any]:
    """ASI[587a9d384c4d]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    OPEN = ctx.OPEN
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    ABS = ctx.ABS
    IFELSE = ctx.IFELSE
    MAX = ctx.MAX
    SUM = ctx.SUM

    # LC
    LC = (
        REF(CLOSE, 1.0)
    )

    # X
    X = (
        ((((CLOSE - LC) + ((CLOSE - OPEN) / 2.0)) + LC) - REF(OPEN, 1.0))
    )

    # AA
    AA = (
        ABS((HIGH - LC))
    )

    # BB
    BB = (
        ABS((LOW - LC))
    )

    # CC
    CC = (
        ABS((HIGH - REF(LOW, 1.0)))
    )

    # DD
    DD = (
        ABS((LC - REF(OPEN, 1.0)))
    )

    # R
    R = (
        IFELSE(
            ctx.logical_and((AA > BB), (AA > CC)),
            ((AA + (BB / 2.0)) + (DD / 4.0)),
            IFELSE(ctx.logical_and((BB > CC), (BB > AA)), ((BB + (AA / 2.0)) + (DD / 4.0)), (CC + (DD / 4.0))),
        )
    )

    # SI
    SI = (
        (((16.0 * X) / R) * MAX(AA, BB))
    )

    # ASI
    ASI = (
        SUM(SI, 0.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_ASI_ASI
    outputs['wh6_ASI_ASI'] = (
        ASI
    )
    return outputs


def formula_004_ATR(ctx: FormulaContext) -> dict[str, Any]:
    """ATR[7e971724d411]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MAX = ctx.MAX
    ABS = ctx.ABS
    REF = ctx.REF
    MA = ctx.MA
    # Locked parameter defaults.
    N = 14.0  # N

    # TR
    TR = (
        MAX(MAX((HIGH - LOW), ABS((REF(CLOSE, 1.0) - HIGH))), ABS((REF(CLOSE, 1.0) - LOW)))
    )

    # ATR
    ATR = (
        MA(TR, N)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_ATR_ATR
    outputs['wh6_ATR_ATR'] = (
        ATR
    )
    # Explicit locked output: wh6_ATR_TR
    outputs['wh6_ATR_TR'] = (
        TR
    )
    return outputs


def formula_005_B3612(ctx: FormulaContext) -> dict[str, Any]:
    """B3612[85515d05832b]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA

    # B36
    B36 = (
        (MA(CLOSE, 3.0) - MA(CLOSE, 6.0))
    )

    # B612
    B612 = (
        (MA(CLOSE, 6.0) - MA(CLOSE, 12.0))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_B3612_B36
    outputs['wh6_B3612_B36'] = (
        B36
    )
    # Explicit locked output: wh6_B3612_B612
    outputs['wh6_B3612_B612'] = (
        B612
    )
    return outputs


def formula_006_BAR(ctx: FormulaContext) -> dict[str, Any]:
    """BAR[25d163f925dd]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    OPEN = ctx.OPEN

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_BAR_BAR
    outputs['wh6_BAR_BAR'] = (
        OPEN
    )
    return outputs


def formula_007_BBIBOLL(ctx: FormulaContext) -> dict[str, Any]:
    """BBIBOLL[cc1c9a4cec06]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    C = ctx.C
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    STD = ctx.STD
    # Locked parameter defaults.
    N = 10.0  # N
    M = 3.0  # M

    # BBIBOLL
    BBIBOLL = (
        ((((MA(C, 3.0) + MA(C, 6.0)) + MA(C, 12.0)) + MA(C, 24.0)) / 4.0)
    )

    # DWN
    DWN = (
        (BBIBOLL - (M * STD(BBIBOLL, N)))
    )

    # UPR
    UPR = (
        (BBIBOLL + (M * STD(BBIBOLL, N)))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_BBIBOLL_BBIBOLL
    outputs['wh6_BBIBOLL_BBIBOLL'] = (
        BBIBOLL
    )
    # Explicit locked output: wh6_BBIBOLL_DWN
    outputs['wh6_BBIBOLL_DWN'] = (
        DWN
    )
    # Explicit locked output: wh6_BBIBOLL_UPR
    outputs['wh6_BBIBOLL_UPR'] = (
        UPR
    )
    return outputs


def formula_008_BBI(ctx: FormulaContext) -> dict[str, Any]:
    """BBI[b585b99484ed]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    # Locked parameter defaults.
    N1 = 3.0  # N1
    N2 = 6.0  # N2
    N3 = 12.0  # N3
    N4 = 24.0  # N4

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_BBI_BBI
    outputs['wh6_BBI_BBI'] = (
        ((((MA(CLOSE, N1) + MA(CLOSE, N2)) + MA(CLOSE, N3)) + MA(CLOSE, N4)) / 4.0)
    )
    return outputs


def formula_009_BIAS(ctx: FormulaContext) -> dict[str, Any]:
    """BIAS[c3c570961585]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    # Locked parameter defaults.
    L1 = 6.0  # L1
    L2 = 12.0  # L2
    L3 = 20.0  # L3

    # BIAS1
    BIAS1 = (
        (((CLOSE - MA(CLOSE, L1)) / MA(CLOSE, L1)) * 100.0)
    )

    # BIAS2
    BIAS2 = (
        (((CLOSE - MA(CLOSE, L2)) / MA(CLOSE, L2)) * 100.0)
    )

    # BIAS3
    BIAS3 = (
        (((CLOSE - MA(CLOSE, L3)) / MA(CLOSE, L3)) * 100.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_BIAS_BIAS1
    outputs['wh6_BIAS_BIAS1'] = (
        BIAS1
    )
    # Explicit locked output: wh6_BIAS_BIAS2
    outputs['wh6_BIAS_BIAS2'] = (
        BIAS2
    )
    # Explicit locked output: wh6_BIAS_BIAS3
    outputs['wh6_BIAS_BIAS3'] = (
        BIAS3
    )
    return outputs


def formula_010_BOLL(ctx: FormulaContext) -> dict[str, Any]:
    """BOLL[78b8e217a7f5]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    STD = ctx.STD
    # Locked parameter defaults.
    N = 26.0  # N
    M = 26.0  # M
    P = 2.0  # P

    # MID
    MID = (
        MA(CLOSE, N)
    )

    # TMP2
    TMP2 = (
        STD(CLOSE, M)
    )

    # BOTTOM
    BOTTOM = (
        (MID - (1.5 * TMP2))
    )

    # TOP
    TOP = (
        (MID + (1.5 * TMP2))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_BOLL_BOTTOM
    outputs['wh6_BOLL_BOTTOM'] = (
        BOTTOM
    )
    # Explicit locked output: wh6_BOLL_MID
    outputs['wh6_BOLL_MID'] = (
        MID
    )
    # Explicit locked output: wh6_BOLL_TOP
    outputs['wh6_BOLL_TOP'] = (
        TOP
    )
    return outputs


def formula_011_CCI(ctx: FormulaContext) -> dict[str, Any]:
    """CCI[3fc4dc01571c]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    AVEDEV = ctx.AVEDEV
    # Locked parameter defaults.
    N = 100.0  # N

    # TYP
    TYP = (
        (((CLOSE + HIGH) + LOW) / 3.0)
    )

    # CCI
    CCI = (
        (((TYP - MA(TYP, N)) / AVEDEV(TYP, N)) / 0.015)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_CCI_CCI
    outputs['wh6_CCI_CCI'] = (
        CCI
    )
    return outputs


def formula_012_CCL(ctx: FormulaContext) -> dict[str, Any]:
    """CCL[6c88ce571d6a]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CCL = ctx.CCL

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_CCL_CCL
    outputs['wh6_CCL_CCL'] = (
        CCL
    )
    return outputs


def formula_013_CDP(ctx: FormulaContext) -> dict[str, Any]:
    """CDP[46525abce43d]: 5 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF

    # CDP
    CDP = (
        (((HIGH + LOW) + CLOSE) / 3.0)
    )

    # PT
    PT = (
        (REF(HIGH, 1.0) - REF(LOW, 1.0))
    )

    # AH
    AH = (
        (CDP + PT)
    )

    # AL
    AL = (
        (CDP - PT)
    )

    # NH
    NH = (
        ((2.0 * CDP) - LOW)
    )

    # NL
    NL = (
        ((2.0 * CDP) - HIGH)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_CDP_AH
    outputs['wh6_CDP_AH'] = (
        AH
    )
    # Explicit locked output: wh6_CDP_AL
    outputs['wh6_CDP_AL'] = (
        AL
    )
    # Explicit locked output: wh6_CDP_CDP
    outputs['wh6_CDP_CDP'] = (
        CDP
    )
    # Explicit locked output: wh6_CDP_NH
    outputs['wh6_CDP_NH'] = (
        NH
    )
    # Explicit locked output: wh6_CDP_NL
    outputs['wh6_CDP_NL'] = (
        NL
    )
    return outputs


def formula_014_CJL(ctx: FormulaContext) -> dict[str, Any]:
    """CJL[3977d607f195]: 1 locked output(s)."""
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    CJLVOL = ctx.CJLVOL
    # Locked parameter defaults.
    M = 1.0  # M

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_CJL_CJL
    outputs['wh6_CJL_CJL'] = (
        CJLVOL(M)
    )
    return outputs


def formula_015_CLOSE(ctx: FormulaContext) -> dict[str, Any]:
    """CLOSE[685de8bb54b6]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_CLOSE_CLOSE
    outputs['wh6_CLOSE_CLOSE'] = (
        CLOSE
    )
    return outputs


def formula_016_CR(ctx: FormulaContext) -> dict[str, Any]:
    """CR[480d4993d264]: 5 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    SUM = ctx.SUM
    MAX = ctx.MAX
    REF = ctx.REF
    MA = ctx.MA
    # Locked parameter defaults.
    N = 26.0  # N
    M1 = 5.0  # M1
    M2 = 10.0  # M2
    M3 = 20.0  # M3
    M4 = 40.0  # M4

    # MID
    MID = (
        (((HIGH + LOW) + CLOSE) / 3.0)
    )

    # CR
    CR = (
        ((SUM(MAX(0.0, (HIGH - REF(MID, 1.0))), N) / SUM(MAX(0.0, (REF(MID, 1.0) - LOW)), N)) * 100.0)
    )

    # CRMA1
    CRMA1 = (
        REF(MA(CR, M1), ((M1 / 2.5) + 1.0))
    )

    # CRMA2
    CRMA2 = (
        REF(MA(CR, M2), ((M2 / 2.5) + 1.0))
    )

    # CRMA3
    CRMA3 = (
        REF(MA(CR, M3), ((M3 / 2.5) + 1.0))
    )

    # CRMA4
    CRMA4 = (
        REF(MA(CR, M4), ((M4 / 2.5) + 1.0))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_CR_CR
    outputs['wh6_CR_CR'] = (
        CR
    )
    # Explicit locked output: wh6_CR_CRMA1
    outputs['wh6_CR_CRMA1'] = (
        CRMA1
    )
    # Explicit locked output: wh6_CR_CRMA2
    outputs['wh6_CR_CRMA2'] = (
        CRMA2
    )
    # Explicit locked output: wh6_CR_CRMA3
    outputs['wh6_CR_CRMA3'] = (
        CRMA3
    )
    # Explicit locked output: wh6_CR_CRMA4
    outputs['wh6_CR_CRMA4'] = (
        CRMA4
    )
    return outputs


def formula_017_DBCD(ctx: FormulaContext) -> dict[str, Any]:
    """DBCD[c836761df84b]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    REF = ctx.REF
    SMA = ctx.SMA
    # Locked parameter defaults.
    N = 5.0  # N
    M = 16.0  # M
    T = 76.0  # T

    # BIAS
    BIAS = (
        ((CLOSE - MA(CLOSE, N)) / MA(CLOSE, N))
    )

    # DIF
    DIF = (
        (BIAS - REF(BIAS, M))
    )

    # DBCD
    DBCD = (
        SMA(DIF, T, 1.0)
    )

    # MM
    MM = (
        MA(DBCD, 5.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_DBCD_DBCD
    outputs['wh6_DBCD_DBCD'] = (
        DBCD
    )
    # Explicit locked output: wh6_DBCD_MM
    outputs['wh6_DBCD_MM'] = (
        MM
    )
    return outputs


def formula_018_DDI(ctx: FormulaContext) -> dict[str, Any]:
    """DDI[745da764bac5]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    IFELSE = ctx.IFELSE
    REF = ctx.REF
    MAX = ctx.MAX
    ABS = ctx.ABS
    SUM = ctx.SUM
    SMA = ctx.SMA
    MA = ctx.MA
    # Locked parameter defaults.
    N = 13.0  # N
    N1 = 30.0  # N1
    M = 10.0  # M
    M1 = 5.0  # M1

    # DMZ
    DMZ = (
        IFELSE(
            ((HIGH + LOW) <= (REF(HIGH, 1.0) + REF(LOW, 1.0))),
            0.0,
            MAX(ABS((HIGH - REF(HIGH, 1.0))), ABS((LOW - REF(LOW, 1.0)))),
        )
    )

    # DMF
    DMF = (
        IFELSE(
            ((HIGH + LOW) >= (REF(HIGH, 1.0) + REF(LOW, 1.0))),
            0.0,
            MAX(ABS((HIGH - REF(HIGH, 1.0))), ABS((LOW - REF(LOW, 1.0)))),
        )
    )

    # DIZ
    DIZ = (
        (SUM(DMZ, N) / (SUM(DMZ, N) + SUM(DMF, N)))
    )

    # DIF
    DIF = (
        (SUM(DMF, N) / (SUM(DMF, N) + SUM(DMZ, N)))
    )

    # DDI
    DDI = (
        (DIZ - DIF)
    )

    # ADDI
    ADDI = (
        SMA(DDI, N1, M)
    )

    # AD
    AD = (
        MA(ADDI, M1)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_DDI_AD
    outputs['wh6_DDI_AD'] = (
        AD
    )
    # Explicit locked output: wh6_DDI_ADDI
    outputs['wh6_DDI_ADDI'] = (
        ADDI
    )
    # Explicit locked output: wh6_DDI_DDI
    outputs['wh6_DDI_DDI'] = (
        DDI
    )
    return outputs


def formula_019_DEMA(ctx: FormulaContext) -> dict[str, Any]:
    """DEMA[1768501f582e]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    EMA = ctx.EMA
    # Locked parameter defaults.
    N = 60.0  # N

    # MA1
    MA1 = (
        EMA(CLOSE, N)
    )

    # DEMA
    DEMA = (
        ((2.0 * MA1) - EMA(MA1, N))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_DEMA_DEMA
    outputs['wh6_DEMA_DEMA'] = (
        DEMA
    )
    return outputs


def formula_020_DKX(ctx: FormulaContext) -> dict[str, Any]:
    """DKX[72aff29ad6a0]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    C = ctx.C
    L = ctx.L
    O = ctx.O
    H = ctx.H
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    MA = ctx.MA
    # Locked parameter defaults.
    M = 10.0  # M

    # A
    A = (
        (((((3.0 * C) + L) + O) + H) / 6.0)
    )

    # B
    B = (
        (
            (
                (
                    (
                        (
                            (
                                (
                                    (
                                        (
                                            (
                                                (
                                                    (
                                                        (
                                                            (
                                                                (
                                                                    (
                                                                        (
                                                                            ((((20.0 * A) + (19.0 * REF(A, 1.0))) + (18.0 * REF(A, 2.0))) + (17.0 * REF(A, 3.0)))
                                                                            +
                                                                            (16.0 * REF(A, 4.0))
                                                                        )
                                                                        +
                                                                        (15.0 * REF(A, 5.0))
                                                                    )
                                                                    +
                                                                    (14.0 * REF(A, 6.0))
                                                                )
                                                                +
                                                                (13.0 * REF(A, 7.0))
                                                            )
                                                            +
                                                            (12.0 * REF(A, 8.0))
                                                        )
                                                        +
                                                        (11.0 * REF(A, 9.0))
                                                    )
                                                    +
                                                    (10.0 * REF(A, 10.0))
                                                )
                                                +
                                                (9.0 * REF(A, 11.0))
                                            )
                                            +
                                            (8.0 * REF(A, 12.0))
                                        )
                                        +
                                        (7.0 * REF(A, 13.0))
                                    )
                                    +
                                    (6.0 * REF(A, 14.0))
                                )
                                +
                                (5.0 * REF(A, 15.0))
                            )
                            +
                            (4.0 * REF(A, 16.0))
                        )
                        +
                        (3.0 * REF(A, 17.0))
                    )
                    +
                    (2.0 * REF(A, 18.0))
                )
                +
                REF(A, 20.0)
            )
            /
            210.0
        )
    )

    # D
    D = (
        MA(B, M)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_DKX_B
    outputs['wh6_DKX_B'] = (
        B
    )
    # Explicit locked output: wh6_DKX_D
    outputs['wh6_DKX_D'] = (
        D
    )
    return outputs


def formula_021_DMA(ctx: FormulaContext) -> dict[str, Any]:
    """DMA[7a6e2e16b102]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    # Locked parameter defaults.
    SHORT = 10.0  # SHORT
    LONG = 50.0  # LONG
    M = 10.0  # M

    # DDD
    DDD = (
        (MA(CLOSE, SHORT) - MA(CLOSE, LONG))
    )

    # AMA
    AMA = (
        MA(DDD, M)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_DMA_AMA
    outputs['wh6_DMA_AMA'] = (
        AMA
    )
    # Explicit locked output: wh6_DMA_DDD
    outputs['wh6_DMA_DDD'] = (
        DDD
    )
    return outputs


def formula_022_DMI(ctx: FormulaContext) -> dict[str, Any]:
    """DMI[4d958bb33736]: 4 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    LOW = ctx.LOW
    HIGH = ctx.HIGH
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    SUM = ctx.SUM
    IFELSE = ctx.IFELSE
    MAX = ctx.MAX
    ABS = ctx.ABS
    MA = ctx.MA
    # Locked parameter defaults.
    N = 14.0  # N
    M = 6.0  # M

    # LD
    LD = (
        (REF(LOW, 1.0) - LOW)
    )

    # HD
    HD = (
        (HIGH - REF(HIGH, 1.0))
    )

    # DMM
    DMM = (
        SUM(IFELSE(ctx.logical_and((LD > 0.0), (LD > HD)), LD, 0.0), N)
    )

    # TR
    TR = (
        SUM(MAX(MAX((HIGH - LOW), ABS((HIGH - REF(CLOSE, 1.0)))), ABS((LOW - REF(CLOSE, 1.0)))), N)
    )

    # MDI
    MDI = (
        ((DMM * 100.0) / TR)
    )

    # DMP
    DMP = (
        SUM(IFELSE(ctx.logical_and((HD > 0.0), (HD > LD)), HD, 0.0), N)
    )

    # PDI
    PDI = (
        ((DMP * 100.0) / TR)
    )

    # ADX
    ADX = (
        MA(((ABS((MDI - PDI)) / (MDI + PDI)) * 100.0), M)
    )

    # ADXR
    ADXR = (
        ((ADX + REF(ADX, M)) / 2.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_DMI_ADX
    outputs['wh6_DMI_ADX'] = (
        ADX
    )
    # Explicit locked output: wh6_DMI_ADXR
    outputs['wh6_DMI_ADXR'] = (
        ADXR
    )
    # Explicit locked output: wh6_DMI_MDI
    outputs['wh6_DMI_MDI'] = (
        MDI
    )
    # Explicit locked output: wh6_DMI_PDI
    outputs['wh6_DMI_PDI'] = (
        PDI
    )
    return outputs


def formula_023_DPO(ctx: FormulaContext) -> dict[str, Any]:
    """DPO[687a5b927b4c]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    MA = ctx.MA

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_DPO_DPO
    outputs['wh6_DPO_DPO'] = (
        (CLOSE - REF(MA(CLOSE, 20.0), 11.0))
    )
    return outputs


def formula_024_EMA2(ctx: FormulaContext) -> dict[str, Any]:
    """EMA2[4da7fae9d327]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    EMA2 = ctx.EMA2
    # Locked parameter defaults.
    N = 10.0  # N

    # MA1
    MA1 = (
        EMA2(CLOSE, N)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_EMA2_MA1
    outputs['wh6_EMA2_MA1'] = (
        MA1
    )
    return outputs


def formula_025_EMA(ctx: FormulaContext) -> dict[str, Any]:
    """EMA[067f3c40e24b]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    EMA = ctx.EMA
    # Locked parameter defaults.
    N = 20.0  # N

    # MA1
    MA1 = (
        EMA(CLOSE, N)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_EMA_MA1
    outputs['wh6_EMA_MA1'] = (
        MA1
    )
    return outputs


def formula_026_ENV(ctx: FormulaContext) -> dict[str, Any]:
    """ENV[999d9e148aed]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    # Locked parameter defaults.
    N1 = 14.0  # N1
    N2 = 6.0  # N2

    # LOWER
    LOWER = (
        (MA(CLOSE, N1) * (1.0 - (N2 / 100.0)))
    )

    # UPPER
    UPPER = (
        (MA(CLOSE, N1) * (1.0 + (N2 / 100.0)))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_ENV_LOWER
    outputs['wh6_ENV_LOWER'] = (
        LOWER
    )
    # Explicit locked output: wh6_ENV_UPPER
    outputs['wh6_ENV_UPPER'] = (
        UPPER
    )
    return outputs


def formula_027_FIBONACCI_BANDS(ctx: FormulaContext) -> dict[str, Any]:
    """FIBONACCI BANDS[95dd251e2618]: 7 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    MAX = ctx.MAX
    ABS = ctx.ABS
    REF = ctx.REF

    # N
    N = (
        20.0
    )

    # MIDDLE
    MIDDLE = (
        MA(CLOSE, N)
    )

    # TR
    TR = (
        MAX(MAX((HIGH - LOW), ABS((REF(CLOSE, 1.0) - HIGH))), ABS((REF(CLOSE, 1.0) - LOW)))
    )

    # ATR
    ATR = (
        MA(TR, N)
    )

    # UPPER1
    UPPER1 = (
        (MIDDLE + (1.0 * ATR))
    )

    # UPPER2
    UPPER2 = (
        (MIDDLE + (2.0 * ATR))
    )

    # UPPER3
    UPPER3 = (
        (MIDDLE + (3.0 * ATR))
    )

    # LOWER1
    LOWER1 = (
        (MIDDLE - (1.0 * ATR))
    )

    # LOWER2
    LOWER2 = (
        (MIDDLE - (2.0 * ATR))
    )

    # LOWER3
    LOWER3 = (
        (MIDDLE - (3.0 * ATR))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_FIBONACCI_BANDS_FIBONACCI_BANDS
    outputs['wh6_FIBONACCI_BANDS_FIBONACCI_BANDS'] = (
        MIDDLE
    )
    # Explicit locked output: wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_2
    outputs['wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_2'] = (
        UPPER1
    )
    # Explicit locked output: wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_3
    outputs['wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_3'] = (
        UPPER2
    )
    # Explicit locked output: wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_4
    outputs['wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_4'] = (
        UPPER3
    )
    # Explicit locked output: wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_5
    outputs['wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_5'] = (
        LOWER1
    )
    # Explicit locked output: wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_6
    outputs['wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_6'] = (
        LOWER2
    )
    # Explicit locked output: wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_7
    outputs['wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_7'] = (
        LOWER3
    )
    return outputs


def formula_028_HCL(ctx: FormulaContext) -> dict[str, Any]:
    """HCL[94addf722c9d]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    # Locked parameter defaults.
    N = 10.0  # N

    # MAC
    MAC = (
        MA(CLOSE, N)
    )

    # MAH
    MAH = (
        MA(HIGH, N)
    )

    # MAL
    MAL = (
        MA(LOW, N)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_HCL_MAC
    outputs['wh6_HCL_MAC'] = (
        MAC
    )
    # Explicit locked output: wh6_HCL_MAH
    outputs['wh6_HCL_MAH'] = (
        MAH
    )
    # Explicit locked output: wh6_HCL_MAL
    outputs['wh6_HCL_MAL'] = (
        MAL
    )
    return outputs


def formula_029_HIGH(ctx: FormulaContext) -> dict[str, Any]:
    """HIGH[4a5b7a67f44a]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    HIGH = ctx.HIGH

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_HIGH_HIGH
    outputs['wh6_HIGH_HIGH'] = (
        HIGH
    )
    return outputs


def formula_030_KDJ(ctx: FormulaContext) -> dict[str, Any]:
    """KDJ[2693ba61e79f]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    LOW = ctx.LOW
    HIGH = ctx.HIGH
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    LLV = ctx.LLV
    HHV = ctx.HHV
    SMA = ctx.SMA
    # Locked parameter defaults.
    N = 9.0  # N
    M1 = 3.0  # M1
    M2 = 3.0  # M2

    # RSV
    RSV = (
        (((CLOSE - LLV(LOW, N)) / (HHV(HIGH, N) - LLV(LOW, N))) * 100.0)
    )

    # K
    K = (
        SMA(RSV, M1, 1.0)
    )

    # D
    D = (
        SMA(K, M2, 1.0)
    )

    # J
    J = (
        ((3.0 * K) - (2.0 * D))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_KDJ_D
    outputs['wh6_KDJ_D'] = (
        D
    )
    # Explicit locked output: wh6_KDJ_J
    outputs['wh6_KDJ_J'] = (
        J
    )
    # Explicit locked output: wh6_KDJ_K
    outputs['wh6_KDJ_K'] = (
        K
    )
    return outputs


def formula_031_KD(ctx: FormulaContext) -> dict[str, Any]:
    """KD[1b3caa4bed83]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    LOW = ctx.LOW
    HIGH = ctx.HIGH
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    LLV = ctx.LLV
    HHV = ctx.HHV
    SMA = ctx.SMA
    # Locked parameter defaults.
    N = 17.0  # N
    M1 = 6.0  # M1
    M2 = 6.0  # M2

    # RSV
    RSV = (
        (((CLOSE - LLV(LOW, N)) / (HHV(HIGH, N) - LLV(LOW, N))) * 100.0)
    )

    # K
    K = (
        SMA(RSV, M1, 1.0)
    )

    # D
    D = (
        SMA(K, M2, 1.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_KD_D
    outputs['wh6_KD_D'] = (
        D
    )
    # Explicit locked output: wh6_KD_K
    outputs['wh6_KD_K'] = (
        K
    )
    return outputs


def formula_032_LON(ctx: FormulaContext) -> dict[str, Any]:
    """LON长线[fe0f90cc8208]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    VOL = ctx.VOL
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    SUM = ctx.SUM
    HHV = ctx.HHV
    LLV = ctx.LLV
    SMA = ctx.SMA
    MA = ctx.MA
    # Locked parameter defaults.
    N = 10.0  # N

    # LC
    LC = (
        REF(CLOSE, 1.0)
    )

    # VID
    VID = (
        (SUM(VOL, 2.0) / ((HHV(HIGH, 2.0) - LLV(LOW, 2.0)) * 100.0))
    )

    # RC
    RC = (
        ((CLOSE - LC) * VID)
    )

    # LONG
    LONG = (
        SUM(RC, 0.0)
    )

    # LONGMA1
    LONGMA1 = (
        SMA(LONG, 10.0, 1.0)
    )

    # LONGMA2
    LONGMA2 = (
        SMA(LONG, 20.0, 1.0)
    )

    # LON
    LON = (
        (LONGMA1 - LONGMA2)
    )

    # LONGMA
    LONGMA = (
        MA(LON, N)
    )

    # LONGT
    LONGT = (
        LON
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_LON_LON
    outputs['wh6_LON_LON'] = (
        LON
    )
    # Explicit locked output: wh6_LON_LONGMA
    outputs['wh6_LON_LONGMA'] = (
        LONGMA
    )
    # Explicit locked output: wh6_LON_LONGT
    outputs['wh6_LON_LONGT'] = (
        LONGT
    )
    return outputs


def formula_033_LOW(ctx: FormulaContext) -> dict[str, Any]:
    """LOW[2e2429934f1e]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    LOW = ctx.LOW

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_LOW_LOW
    outputs['wh6_LOW_LOW'] = (
        LOW
    )
    return outputs


def formula_034_MACD(ctx: FormulaContext) -> dict[str, Any]:
    """MACD[8ec10f3b6154]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    EMA = ctx.EMA
    # Locked parameter defaults.
    SHORT = 12.0  # SHORT
    LONG = 26.0  # LONG
    M = 9.0  # M

    # DIFF
    DIFF = (
        (EMA(CLOSE, SHORT) - EMA(CLOSE, LONG))
    )

    # DEA
    DEA = (
        EMA(DIFF, M)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_MACD_DEA
    outputs['wh6_MACD_DEA'] = (
        DEA
    )
    # Explicit locked output: wh6_MACD_DIFF
    outputs['wh6_MACD_DIFF'] = (
        DIFF
    )
    # Explicit locked output: wh6_MACD_MACD
    outputs['wh6_MACD_MACD'] = (
        (2.0 * (DIFF - DEA))
    )
    return outputs


def formula_035_MASS(ctx: FormulaContext) -> dict[str, Any]:
    """MASS[ee67c0f903d7]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    SUM = ctx.SUM
    EMA = ctx.EMA
    # Locked parameter defaults.
    N1 = 9.0  # N1
    N2 = 25.0  # N2

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_MASS_MASS
    outputs['wh6_MASS_MASS'] = (
        SUM((EMA((HIGH - LOW), N1) / EMA(EMA((HIGH - LOW), N1), N1)), N2)
    )
    return outputs


def formula_036_MA(ctx: FormulaContext) -> dict[str, Any]:
    """MA[070288e4d7c8]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    # Locked parameter defaults.
    N = 10.0  # N

    # MA1
    MA1 = (
        MA(CLOSE, N)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_MA_MA1
    outputs['wh6_MA_MA1'] = (
        MA1
    )
    return outputs


def formula_037_MFI(ctx: FormulaContext) -> dict[str, Any]:
    """MFI[bfc4218bf782]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    CLOSE = ctx.CLOSE
    VOL = ctx.VOL
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    SUM = ctx.SUM
    IFELSE = ctx.IFELSE
    REF = ctx.REF
    # Locked parameter defaults.
    N = 14.0  # N

    # TYP
    TYP = (
        (((HIGH + LOW) + CLOSE) / 3.0)
    )

    # MR
    MR = (
        (
            SUM(IFELSE((TYP > REF(TYP, 1.0)), (TYP * VOL), 0.0), N)
            /
            SUM(IFELSE((TYP < REF(TYP, 1.0)), (TYP * VOL), 0.0), N)
        )
    )

    # MFI
    MFI = (
        (100.0 - (100.0 / (1.0 + MR)))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_MFI_MFI
    outputs['wh6_MFI_MFI'] = (
        MFI
    )
    return outputs


def formula_038_MFI(ctx: FormulaContext) -> dict[str, Any]:
    """资金流量MFI[d54cecd8882f]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    CLOSE = ctx.CLOSE
    VOL = ctx.VOL
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    IF = ctx.IF
    REF = ctx.REF
    SUM = ctx.SUM

    # TP
    TP = (
        (((HIGH + LOW) + CLOSE) / 3.0)
    )

    # MF
    MF = (
        (TP * VOL)
    )

    # UPMF
    UPMF = (
        IF((TP > REF(TP, 1.0)), MF, 0.0)
    )

    # N
    N = (
        14.0
    )

    # POSMF
    POSMF = (
        SUM(UPMF, N)
    )

    # DNMF
    DNMF = (
        IF((TP < REF(TP, 1.0)), MF, 0.0)
    )

    # NEGMF
    NEGMF = (
        SUM(DNMF, N)
    )

    # MFR
    MFR = (
        (POSMF / NEGMF)
    )

    # MFI
    MFI = (
        (100.0 - (100.0 / (1.0 + MFR)))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_MFI_MFI_2
    outputs['wh6_MFI_MFI_2'] = (
        MFI
    )
    return outputs


def formula_039_MICD(ctx: FormulaContext) -> dict[str, Any]:
    """MICD[c6480329fe65]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    SMA = ctx.SMA
    MA = ctx.MA
    # Locked parameter defaults.
    N = 8.0  # N
    N1 = 3.0  # N1
    N2 = 8.0  # N2

    # MI
    MI = (
        (CLOSE - REF(CLOSE, 1.0))
    )

    # AMI
    AMI = (
        SMA(MI, N, 1.0)
    )

    # DIF
    DIF = (
        (MA(REF(AMI, 1.0), N1) - MA(REF(AMI, 1.0), N2))
    )

    # MICD
    MICD = (
        SMA(DIF, 10.0, 1.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_MICD_DIF
    outputs['wh6_MICD_DIF'] = (
        DIF
    )
    # Explicit locked output: wh6_MICD_MICD
    outputs['wh6_MICD_MICD'] = (
        MICD
    )
    return outputs


def formula_040_MIKE(ctx: FormulaContext) -> dict[str, Any]:
    """MIKE[e35a26cbc933]: 6 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    HHV = ctx.HHV
    LLV = ctx.LLV
    # Locked parameter defaults.
    N = 12.0  # N

    # TYP
    TYP = (
        (((HIGH + LOW) + CLOSE) / 3.0)
    )

    # HH
    HH = (
        HHV(HIGH, N)
    )

    # LL
    LL = (
        LLV(LOW, N)
    )

    # MR
    MR = (
        (TYP + (HH - LL))
    )

    # MS
    MS = (
        (TYP - (HH - LL))
    )

    # SR
    SR = (
        ((2.0 * HH) - LL)
    )

    # SS
    SS = (
        ((2.0 * LL) - HH)
    )

    # WR
    WR = (
        (TYP + (TYP - LL))
    )

    # WS
    WS = (
        (TYP - (HH - TYP))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_MIKE_MR
    outputs['wh6_MIKE_MR'] = (
        MR
    )
    # Explicit locked output: wh6_MIKE_MS
    outputs['wh6_MIKE_MS'] = (
        MS
    )
    # Explicit locked output: wh6_MIKE_SR
    outputs['wh6_MIKE_SR'] = (
        SR
    )
    # Explicit locked output: wh6_MIKE_SS
    outputs['wh6_MIKE_SS'] = (
        SS
    )
    # Explicit locked output: wh6_MIKE_WR
    outputs['wh6_MIKE_WR'] = (
        WR
    )
    # Explicit locked output: wh6_MIKE_WS
    outputs['wh6_MIKE_WS'] = (
        WS
    )
    return outputs


def formula_041_MI(ctx: FormulaContext) -> dict[str, Any]:
    """MI[d43023fd036d]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    SMA = ctx.SMA
    # Locked parameter defaults.
    N = 12.0  # N

    # A
    A = (
        (CLOSE - REF(CLOSE, N))
    )

    # MI
    MI = (
        SMA(A, N, 1.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_MI_A
    outputs['wh6_MI_A'] = (
        A
    )
    # Explicit locked output: wh6_MI_MI
    outputs['wh6_MI_MI'] = (
        MI
    )
    return outputs


def formula_042_MTM(ctx: FormulaContext) -> dict[str, Any]:
    """MTM[b2ed05216bb0]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    MA = ctx.MA
    # Locked parameter defaults.
    N = 6.0  # N
    N1 = 6.0  # N1

    # MTM
    MTM = (
        (CLOSE - REF(CLOSE, N))
    )

    # MTMMA
    MTMMA = (
        MA(MTM, N1)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_MTM_MTM
    outputs['wh6_MTM_MTM'] = (
        MTM
    )
    # Explicit locked output: wh6_MTM_MTMMA
    outputs['wh6_MTM_MTMMA'] = (
        MTMMA
    )
    return outputs


def formula_043_MV(ctx: FormulaContext) -> dict[str, Any]:
    """MV[a1fbc33a6fac]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    VOL = ctx.VOL
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    SMA = ctx.SMA
    # Locked parameter defaults.
    N = 10.0  # N
    M = 20.0  # M

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_MV_MV
    outputs['wh6_MV_MV'] = (
        VOL
    )
    # Explicit locked output: wh6_MV_MV_2
    outputs['wh6_MV_MV_2'] = (
        SMA(VOL, N, 1.0)
    )
    # Explicit locked output: wh6_MV_MV_3
    outputs['wh6_MV_MV_3'] = (
        SMA(VOL, M, 1.0)
    )
    return outputs


def formula_044_MYFORCAST(ctx: FormulaContext) -> dict[str, Any]:
    """MYFORCAST[03b05cf478b3]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    FORCAST = ctx.FORCAST
    REF = ctx.REF
    # Locked parameter defaults.
    N = 10.0  # N

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_MYFORCAST_MYFORCAST
    outputs['wh6_MYFORCAST_MYFORCAST'] = (
        FORCAST(REF(CLOSE, 1.0), N)
    )
    return outputs


def formula_045_OBV(ctx: FormulaContext) -> dict[str, Any]:
    """OBV[2ba4cc6f407d]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    VOL = ctx.VOL
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    SUM = ctx.SUM
    IFELSE = ctx.IFELSE
    REF = ctx.REF

    # OBVMA
    OBVMA = (
        MA(
            SUM(IFELSE((CLOSE > REF(CLOSE, 1.0)), VOL, IFELSE((CLOSE < REF(CLOSE, 1.0)), (-VOL), 0.0)), 0.0),
            20.0,
        )
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_OBV_OBV
    outputs['wh6_OBV_OBV'] = (
        SUM(IFELSE((CLOSE > REF(CLOSE, 1.0)), VOL, IFELSE((CLOSE < REF(CLOSE, 1.0)), (-VOL), 0.0)), 0.0)
    )
    # Explicit locked output: wh6_OBV_OBVMA
    outputs['wh6_OBV_OBVMA'] = (
        OBVMA
    )
    return outputs


def formula_046_OPEN(ctx: FormulaContext) -> dict[str, Any]:
    """OPEN[32f0bacd5e2f]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    OPEN = ctx.OPEN

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_OPEN_OPEN
    outputs['wh6_OPEN_OPEN'] = (
        OPEN
    )
    return outputs


def formula_047_PRICEOSC(ctx: FormulaContext) -> dict[str, Any]:
    """PRICEOSC[83cd869938cf]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    # Locked parameter defaults.
    LONG = 26.0  # LONG
    SHORT = 12.0  # SHORT

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_PRICEOSC_PRICEOSC
    outputs['wh6_PRICEOSC_PRICEOSC'] = (
        (((MA(CLOSE, SHORT) - MA(CLOSE, LONG)) / MA(CLOSE, SHORT)) * 100.0)
    )
    return outputs


def formula_048_PSY(ctx: FormulaContext) -> dict[str, Any]:
    """PSY[cdf8c42ae903]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    COUNT = ctx.COUNT
    REF = ctx.REF
    MA = ctx.MA
    # Locked parameter defaults.
    N = 12.0  # N
    M = 6.0  # M

    # PSY
    PSY = (
        ((COUNT((CLOSE > REF(CLOSE, 1.0)), N) / N) * 100.0)
    )

    # PSYMA
    PSYMA = (
        MA(PSY, M)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_PSY_PSY
    outputs['wh6_PSY_PSY'] = (
        PSY
    )
    # Explicit locked output: wh6_PSY_PSYMA
    outputs['wh6_PSY_PSYMA'] = (
        PSYMA
    )
    return outputs


def formula_049_PUBU(ctx: FormulaContext) -> dict[str, Any]:
    """PUBU[79271ae789a6]: 6 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    EMA = ctx.EMA
    MA = ctx.MA
    # Locked parameter defaults.
    M1 = 4.0  # M1
    M2 = 6.0  # M2
    M3 = 9.0  # M3
    M4 = 13.0  # M4
    M5 = 18.0  # M5
    M6 = 24.0  # M6

    # PB1
    PB1 = (
        (((EMA(CLOSE, M1) + MA(CLOSE, (M1 * 2.0))) + MA(CLOSE, (M1 * 4.0))) / 3.0)
    )

    # PB2
    PB2 = (
        (((EMA(CLOSE, M2) + MA(CLOSE, (M2 * 2.0))) + MA(CLOSE, (M2 * 4.0))) / 3.0)
    )

    # PB3
    PB3 = (
        (((EMA(CLOSE, M3) + MA(CLOSE, (M3 * 2.0))) + MA(CLOSE, (M3 * 4.0))) / 3.0)
    )

    # PB4
    PB4 = (
        (((EMA(CLOSE, M4) + MA(CLOSE, (M4 * 2.0))) + MA(CLOSE, (M4 * 4.0))) / 3.0)
    )

    # PB5
    PB5 = (
        (((EMA(CLOSE, M5) + MA(CLOSE, (M5 * 2.0))) + MA(CLOSE, (M5 * 4.0))) / 3.0)
    )

    # PB6
    PB6 = (
        (((EMA(CLOSE, M6) + MA(CLOSE, (M6 * 2.0))) + MA(CLOSE, (M6 * 4.0))) / 3.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_PUBU_PB1
    outputs['wh6_PUBU_PB1'] = (
        PB1
    )
    # Explicit locked output: wh6_PUBU_PB2
    outputs['wh6_PUBU_PB2'] = (
        PB2
    )
    # Explicit locked output: wh6_PUBU_PB3
    outputs['wh6_PUBU_PB3'] = (
        PB3
    )
    # Explicit locked output: wh6_PUBU_PB4
    outputs['wh6_PUBU_PB4'] = (
        PB4
    )
    # Explicit locked output: wh6_PUBU_PB5
    outputs['wh6_PUBU_PB5'] = (
        PB5
    )
    # Explicit locked output: wh6_PUBU_PB6
    outputs['wh6_PUBU_PB6'] = (
        PB6
    )
    return outputs


def formula_050_PVT(ctx: FormulaContext) -> dict[str, Any]:
    """PVT[5004435db5f8]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    VOL = ctx.VOL
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    SUM = ctx.SUM
    REF = ctx.REF

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_PVT_PVT
    outputs['wh6_PVT_PVT'] = (
        SUM((((CLOSE - REF(CLOSE, 1.0)) / REF(CLOSE, 1.0)) * VOL), 0.0)
    )
    return outputs


def formula_051_QHLSR(ctx: FormulaContext) -> dict[str, Any]:
    """QHLSR[42615538a4be]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    VOL = ctx.VOL
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    SUM = ctx.SUM
    IFELSE = ctx.IFELSE
    ABS = ctx.ABS

    # QHL
    QHL = (
        (
            (CLOSE - REF(CLOSE, 1.0))
            -
            (((VOL - REF(VOL, 1.0)) * (REF(HIGH, 1.0) - REF(LOW, 1.0))) / REF(VOL, 1.0))
        )
    )

    # E
    E = (
        SUM(IFELSE((QHL > 0.0), QHL, 0.0), 10.0)
    )

    # F
    F = (
        ABS(SUM(IFELSE((QHL < 0.0), QHL, 0.0), 10.0))
    )

    # G
    G = (
        (E / (E + F))
    )

    # QHL10
    QHL10 = (
        G
    )

    # A
    A = (
        SUM(IFELSE((QHL > 0.0), QHL, 0.0), 5.0)
    )

    # B
    B = (
        ABS(SUM(IFELSE((QHL < 0.0), QHL, 0.0), 5.0))
    )

    # D
    D = (
        (A / (A + B))
    )

    # QHL5
    QHL5 = (
        IFELSE(
            (SUM(IFELSE((QHL > 0.0), 1.0, 0.0), 5.0) == 5.0),
            1.0,
            IFELSE((SUM(IFELSE((QHL < 0.0), 1.0, 0.0), 5.0) == 5.0), 0.0, D),
        )
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_QHLSR_QHL10
    outputs['wh6_QHLSR_QHL10'] = (
        QHL10
    )
    # Explicit locked output: wh6_QHLSR_QHL5
    outputs['wh6_QHLSR_QHL5'] = (
        QHL5
    )
    return outputs


def formula_052_RCCD(ctx: FormulaContext) -> dict[str, Any]:
    """RCCD[781a794ee92d]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    SMA = ctx.SMA
    MA = ctx.MA
    # Locked parameter defaults.
    N = 59.0  # N
    N1 = 21.0  # N1
    N2 = 28.0  # N2

    # RC
    RC = (
        (CLOSE / REF(CLOSE, N))
    )

    # ARC
    ARC = (
        SMA(REF(RC, 1.0), N, 1.0)
    )

    # DIF
    DIF = (
        (MA(REF(ARC, 1.0), N1) - MA(REF(ARC, 1.0), N2))
    )

    # RCCD
    RCCD = (
        SMA(DIF, N, 1.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_RCCD_DIF
    outputs['wh6_RCCD_DIF'] = (
        DIF
    )
    # Explicit locked output: wh6_RCCD_RCCD
    outputs['wh6_RCCD_RCCD'] = (
        RCCD
    )
    return outputs


def formula_053_RC(ctx: FormulaContext) -> dict[str, Any]:
    """RC[41f33d69be01]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    SMA = ctx.SMA
    # Locked parameter defaults.
    N = 50.0  # N

    # RC
    RC = (
        (CLOSE / REF(CLOSE, N))
    )

    # ARC
    ARC = (
        SMA(REF(RC, 1.0), N, 1.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_RC_ARC
    outputs['wh6_RC_ARC'] = (
        ARC
    )
    return outputs


def formula_054_ROC(ctx: FormulaContext) -> dict[str, Any]:
    """ROC[1f4d053ed38c]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    MA = ctx.MA
    # Locked parameter defaults.
    N = 24.0  # N
    M = 20.0  # M

    # ROC
    ROC = (
        (((CLOSE - REF(CLOSE, N)) / REF(CLOSE, N)) * 100.0)
    )

    # ROCMA
    ROCMA = (
        MA(ROC, M)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_ROC_ROC
    outputs['wh6_ROC_ROC'] = (
        ROC
    )
    # Explicit locked output: wh6_ROC_ROCMA
    outputs['wh6_ROC_ROCMA'] = (
        ROCMA
    )
    return outputs


def formula_055_ROC(ctx: FormulaContext) -> dict[str, Any]:
    """ROC有界限版[61284b24cb4c]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    MA = ctx.MA
    ABS = ctx.ABS
    # Locked parameter defaults.
    N = 24.0  # N
    M = 24.0  # M
    K = 8.0  # K

    # ROC
    ROC = (
        (((CLOSE - REF(CLOSE, N)) / REF(CLOSE, N)) * 100.0)
    )

    # ROCMA
    ROCMA = (
        MA(ROC, M)
    )

    # ROC_B
    ROC_B = (
        (ROC / (ABS(ROC) + K))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_ROC_ROCMA_2
    outputs['wh6_ROC_ROCMA_2'] = (
        ROCMA
    )
    # Explicit locked output: wh6_ROC_ROC_2
    outputs['wh6_ROC_ROC_2'] = (
        ROC
    )
    # Explicit locked output: wh6_ROC_ROC_B
    outputs['wh6_ROC_ROC_B'] = (
        ROC_B
    )
    return outputs


def formula_056_RSIS(ctx: FormulaContext) -> dict[str, Any]:
    """RSIS[044808e77e15]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    SMA = ctx.SMA
    MAX = ctx.MAX
    ABS = ctx.ABS
    HHV = ctx.HHV
    LLV = ctx.LLV
    IF = ctx.IF
    # Locked parameter defaults.
    N1 = 120.0  # N1
    N2 = 240.0  # N2

    # X_LC
    X_LC = (
        REF(CLOSE, 1.0)
    )

    # X_RSI1_VAL
    X_RSI1_VAL = (
        ((SMA(MAX((CLOSE - X_LC), 0.0), N1, 1.0) / SMA(ABS((CLOSE - X_LC)), N1, 1.0)) * 100.0)
    )

    # X_RSI1_MAX
    X_RSI1_MAX = (
        HHV(X_RSI1_VAL, N1)
    )

    # X_RSI1_MIN
    X_RSI1_MIN = (
        LLV(X_RSI1_VAL, N1)
    )

    # X_RSIS1_VAL
    X_RSIS1_VAL = (
        IF(
            (X_RSI1_MAX != X_RSI1_MIN),
            (((X_RSI1_VAL - X_RSI1_MIN) / (X_RSI1_MAX - X_RSI1_MIN)) * 100.0),
            0.0,
        )
    )

    # RSIS1
    RSIS1 = (
        X_RSIS1_VAL
    )

    # X_RSI2_VAL
    X_RSI2_VAL = (
        ((SMA(MAX((CLOSE - X_LC), 0.0), N2, 1.0) / SMA(ABS((CLOSE - X_LC)), N2, 1.0)) * 100.0)
    )

    # X_RSI2_MAX
    X_RSI2_MAX = (
        HHV(X_RSI2_VAL, N2)
    )

    # X_RSI2_MIN
    X_RSI2_MIN = (
        LLV(X_RSI2_VAL, N2)
    )

    # X_RSIS2_VAL
    X_RSIS2_VAL = (
        IF(
            (X_RSI2_MAX != X_RSI2_MIN),
            (((X_RSI2_VAL - X_RSI2_MIN) / (X_RSI2_MAX - X_RSI2_MIN)) * 100.0),
            0.0,
        )
    )

    # RSIS2
    RSIS2 = (
        X_RSIS2_VAL
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_RSIS_RSIS1
    outputs['wh6_RSIS_RSIS1'] = (
        RSIS1
    )
    # Explicit locked output: wh6_RSIS_RSIS2
    outputs['wh6_RSIS_RSIS2'] = (
        RSIS2
    )
    return outputs


def formula_057_RSI(ctx: FormulaContext) -> dict[str, Any]:
    """RSI[7c1ddc0b3faa]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    SMA = ctx.SMA
    MAX = ctx.MAX
    ABS = ctx.ABS
    # Locked parameter defaults.
    N1 = 8.0  # N1
    N2 = 14.0  # N2

    # LC
    LC = (
        REF(CLOSE, 1.0)
    )

    # RSI1
    RSI1 = (
        ((SMA(MAX((CLOSE - LC), 0.0), N1, 1.0) / SMA(ABS((CLOSE - LC)), N1, 1.0)) * 100.0)
    )

    # RSI2
    RSI2 = (
        ((SMA(MAX((CLOSE - LC), 0.0), N2, 1.0) / SMA(ABS((CLOSE - LC)), N2, 1.0)) * 100.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_RSI_RSI1
    outputs['wh6_RSI_RSI1'] = (
        RSI1
    )
    # Explicit locked output: wh6_RSI_RSI2
    outputs['wh6_RSI_RSI2'] = (
        RSI2
    )
    return outputs


def formula_058_RSI_WILDER(ctx: FormulaContext) -> dict[str, Any]:
    """RSI_WILDER[96e490f3b509]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    IF = ctx.IF
    EMA = ctx.EMA
    # Locked parameter defaults.
    N = 18.0  # N
    N_YELLOW = 9.0  # N_YELLOW

    # LC
    LC = (
        REF(CLOSE, 1.0)
    )

    # GAIN
    GAIN = (
        IF((CLOSE > LC), (CLOSE - LC), 0.0)
    )

    # AVG_GAIN
    AVG_GAIN = (
        EMA(GAIN, N)
    )

    # LOSS
    LOSS = (
        IF((CLOSE < LC), (LC - CLOSE), 0.0)
    )

    # AVG_LOSS
    AVG_LOSS = (
        EMA(LOSS, N)
    )

    # RS
    RS = (
        (AVG_GAIN / AVG_LOSS)
    )

    # RSI1
    RSI1 = (
        (100.0 - (100.0 / (1.0 + RS)))
    )

    # RSI2
    RSI2 = (
        EMA(RSI1, N_YELLOW)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_RSI_WILDER_RSI1
    outputs['wh6_RSI_WILDER_RSI1'] = (
        RSI1
    )
    # Explicit locked output: wh6_RSI_WILDER_RSI2
    outputs['wh6_RSI_WILDER_RSI2'] = (
        RSI2
    )
    return outputs


def formula_059_SAR1(ctx: FormulaContext) -> dict[str, Any]:
    """SAR1[5e35acba7fa0]: 1 locked output(s)."""
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    SAR1 = ctx.SAR1
    # Locked parameter defaults.
    N = 4.0  # N
    STEP = 2.0  # STEP
    MVALUE = 2.0  # MVALUE

    # STEP1
    STEP1 = (
        (STEP / 100.0)
    )

    # MVALUE1
    MVALUE1 = (
        (MVALUE / 10.0)
    )

    # SARLINE
    SARLINE = (
        SAR1(N, STEP1, MVALUE1)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_SAR1_SARLINE
    outputs['wh6_SAR1_SARLINE'] = (
        SARLINE
    )
    return outputs


def formula_060_SAR(ctx: FormulaContext) -> dict[str, Any]:
    """SAR[699677c4dbee]: 1 locked output(s)."""
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    SAR = ctx.SAR
    # Locked parameter defaults.
    N = 4.0  # N
    STEP = 2.0  # STEP
    MVALUE = 20.0  # MVALUE

    # STEP1
    STEP1 = (
        (STEP / 100.0)
    )

    # MVALUE1
    MVALUE1 = (
        (MVALUE / 100.0)
    )

    # SARLINE
    SARLINE = (
        SAR(N, STEP1, MVALUE1)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_SAR_SARLINE
    outputs['wh6_SAR_SARLINE'] = (
        SARLINE
    )
    return outputs


def formula_061_SHORT(ctx: FormulaContext) -> dict[str, Any]:
    """SHORT短线[c908591ee874]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    VOL = ctx.VOL
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    REF = ctx.REF
    # Locked parameter defaults.
    N = 5.0  # N

    # JC2
    JC2 = (
        (((CLOSE - MA(CLOSE, 24.0)) / MA(CLOSE, 24.0)) * 100.0)
    )

    # VOL1
    VOL1 = (
        MA(((VOL - REF(VOL, 1.0)) / REF(VOL, 1.0)), 5.0)
    )

    # SHORT
    SHORT = (
        (JC2 * (1.0 + VOL1))
    )

    # SHORTMA
    SHORTMA = (
        MA(SHORT, N)
    )

    # SHORTT
    SHORTT = (
        SHORT
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_SHORT_SHORT
    outputs['wh6_SHORT_SHORT'] = (
        SHORT
    )
    # Explicit locked output: wh6_SHORT_SHORTMA
    outputs['wh6_SHORT_SHORTMA'] = (
        SHORTMA
    )
    # Explicit locked output: wh6_SHORT_SHORTT
    outputs['wh6_SHORT_SHORTT'] = (
        SHORTT
    )
    return outputs


def formula_062_SLOWKD(ctx: FormulaContext) -> dict[str, Any]:
    """SLOWKD[73ec6bbc6f5d]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    LOW = ctx.LOW
    HIGH = ctx.HIGH
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    LLV = ctx.LLV
    HHV = ctx.HHV
    SMA = ctx.SMA
    # Locked parameter defaults.
    N = 9.0  # N
    M1 = 3.0  # M1
    M2 = 3.0  # M2
    M3 = 3.0  # M3

    # RSV
    RSV = (
        (((CLOSE - LLV(LOW, N)) / (HHV(HIGH, N) - LLV(LOW, N))) * 100.0)
    )

    # FASTK
    FASTK = (
        SMA(RSV, M1, 1.0)
    )

    # K
    K = (
        SMA(FASTK, M2, 1.0)
    )

    # D
    D = (
        SMA(K, M3, 1.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_SLOWKD_D
    outputs['wh6_SLOWKD_D'] = (
        D
    )
    # Explicit locked output: wh6_SLOWKD_K
    outputs['wh6_SLOWKD_K'] = (
        K
    )
    return outputs


def formula_063_SMA(ctx: FormulaContext) -> dict[str, Any]:
    """SMA[cd85e36bfc6e]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    SMA = ctx.SMA
    # Locked parameter defaults.
    N = 6.0  # N

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_SMA_SMA
    outputs['wh6_SMA_SMA'] = (
        SMA(CLOSE, N, 2.0)
    )
    return outputs


def formula_064_SP(ctx: FormulaContext) -> dict[str, Any]:
    """SP[5922aa5dbc05]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    SETTLE = ctx.SETTLE

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_SP_SP
    outputs['wh6_SP_SP'] = (
        SETTLE
    )
    return outputs


def formula_065_SRDM(ctx: FormulaContext) -> dict[str, Any]:
    """SRDM[56994753572a]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    IFELSE = ctx.IFELSE
    REF = ctx.REF
    MAX = ctx.MAX
    ABS = ctx.ABS
    MA = ctx.MA
    SMA = ctx.SMA
    # Locked parameter defaults.
    N = 30.0  # N

    # DMZ
    DMZ = (
        IFELSE(
            ((HIGH + LOW) <= (REF(HIGH, 1.0) + REF(LOW, 1.0))),
            0.0,
            MAX(ABS((HIGH - REF(HIGH, 1.0))), ABS((LOW - REF(LOW, 1.0)))),
        )
    )

    # ADMZ
    ADMZ = (
        MA(DMZ, 10.0)
    )

    # DMF
    DMF = (
        IFELSE(
            ((HIGH + LOW) >= (REF(HIGH, 1.0) + REF(LOW, 1.0))),
            0.0,
            MAX(ABS((HIGH - REF(HIGH, 1.0))), ABS((LOW - REF(LOW, 1.0)))),
        )
    )

    # ADMF
    ADMF = (
        MA(DMF, 10.0)
    )

    # SRDM
    SRDM = (
        IFELSE((ADMZ > ADMF), ((ADMZ - ADMF) / ADMZ), IFELSE((ADMZ == ADMF), 0.0, ((ADMZ - ADMF) / ADMF)))
    )

    # ASRDM
    ASRDM = (
        SMA(SRDM, N, 1.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_SRDM_ASRDM
    outputs['wh6_SRDM_ASRDM'] = (
        ASRDM
    )
    # Explicit locked output: wh6_SRDM_SRDM
    outputs['wh6_SRDM_SRDM'] = (
        SRDM
    )
    return outputs


def formula_066_SRMI(ctx: FormulaContext) -> dict[str, Any]:
    """SRMI[cb604fa33bae]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    IFELSE = ctx.IFELSE
    REF = ctx.REF
    # Locked parameter defaults.
    N = 9.0  # N

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_SRMI_SRMI
    outputs['wh6_SRMI_SRMI'] = (
        IFELSE(
            (CLOSE < REF(CLOSE, N)),
            ((CLOSE - REF(CLOSE, N)) / REF(CLOSE, N)),
            IFELSE((CLOSE == REF(CLOSE, N)), 0.0, ((CLOSE - REF(CLOSE, N)) / CLOSE)),
        )
    )
    return outputs


def formula_067_STOCHASTIC_RSI(ctx: FormulaContext) -> dict[str, Any]:
    """STOCHASTIC RSI[977acef3e03a]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    MAX = ctx.MAX
    ABS = ctx.ABS
    SMA = ctx.SMA
    HHV = ctx.HHV
    LLV = ctx.LLV
    IF = ctx.IF

    # LC
    LC = (
        REF(CLOSE, 1.0)
    )

    # U
    U = (
        MAX((CLOSE - LC), 0.0)
    )

    # N_RSI
    N_RSI = (
        7.0
    )

    # D
    D = (
        ABS((CLOSE - LC))
    )

    # RSI_BASE
    RSI_BASE = (
        ((SMA(U, N_RSI, 1.0) / SMA(D, N_RSI, 1.0)) * 100.0)
    )

    # N_SR
    N_SR = (
        7.0
    )

    # RSI_HHV
    RSI_HHV = (
        HHV(RSI_BASE, N_SR)
    )

    # RSI_LLV
    RSI_LLV = (
        LLV(RSI_BASE, N_SR)
    )

    # STOCH_RSI_RAW
    STOCH_RSI_RAW = (
        IF((RSI_HHV == RSI_LLV), 50.0, (((RSI_BASE - RSI_LLV) / (RSI_HHV - RSI_LLV)) * 100.0))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_STOCHASTIC_RSI_RSI_BASE
    outputs['wh6_STOCHASTIC_RSI_RSI_BASE'] = (
        RSI_BASE
    )
    # Explicit locked output: wh6_STOCHASTIC_RSI_STOCH_RSI_RAW
    outputs['wh6_STOCHASTIC_RSI_STOCH_RSI_RAW'] = (
        STOCH_RSI_RAW
    )
    return outputs


def formula_068_VOLATILITY(ctx: FormulaContext) -> dict[str, Any]:
    """VOLATILITY[12805f344569]: 1 locked output(s)."""
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    VOLATILITY = ctx.VOLATILITY
    # Locked parameter defaults.
    N = 60.0  # N

    # 历史波动率
    历史波动率 = (
        (VOLATILITY(N) * 100.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_VOLATILITY_u_c40446c0
    outputs['wh6_VOLATILITY_u_c40446c0'] = (
        历史波动率
    )
    return outputs


def formula_069_VOSC(ctx: FormulaContext) -> dict[str, Any]:
    """VOSC[e4af5638db70]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    VOL = ctx.VOL
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    # Locked parameter defaults.
    SHORT = 12.0  # SHORT
    LONG = 26.0  # LONG

    # OBVMA
    OBVMA = (
        MA((((MA(VOL, SHORT) - MA(VOL, LONG)) / MA(VOL, SHORT)) * 100.0), 20.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_VOSC_OBVMA
    outputs['wh6_VOSC_OBVMA'] = (
        OBVMA
    )
    # Explicit locked output: wh6_VOSC_VOSC
    outputs['wh6_VOSC_VOSC'] = (
        (((MA(VOL, SHORT) - MA(VOL, LONG)) / MA(VOL, SHORT)) * 100.0)
    )
    return outputs


def formula_070_VROC(ctx: FormulaContext) -> dict[str, Any]:
    """VROC[b1d6fae4c713]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    VOL = ctx.VOL
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    # Locked parameter defaults.
    N = 12.0  # N

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_VROC_VROC
    outputs['wh6_VROC_VROC'] = (
        (((VOL - REF(VOL, N)) / REF(VOL, N)) * 100.0)
    )
    return outputs


def formula_071_VRSI(ctx: FormulaContext) -> dict[str, Any]:
    """VRSI[2a4be8ff07d3]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    VOL = ctx.VOL
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    SMA = ctx.SMA
    MAX = ctx.MAX
    REF = ctx.REF
    ABS = ctx.ABS
    # Locked parameter defaults.
    N = 6.0  # N

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_VRSI_VRSI
    outputs['wh6_VRSI_VRSI'] = (
        ((SMA(MAX((VOL - REF(VOL, 1.0)), 0.0), N, 1.0) / SMA(ABS((VOL - REF(VOL, 1.0))), N, 1.0)) * 100.0)
    )
    return outputs


def formula_072_VR(ctx: FormulaContext) -> dict[str, Any]:
    """VR[ecda4391a2c2]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    VOL = ctx.VOL
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    SUM = ctx.SUM
    IFELSE = ctx.IFELSE
    # Locked parameter defaults.
    N = 25.0  # N

    # LC
    LC = (
        REF(CLOSE, 1.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_VR_VR
    outputs['wh6_VR_VR'] = (
        ((SUM(IFELSE((CLOSE > LC), VOL, 0.0), N) / SUM(IFELSE((CLOSE <= LC), VOL, 0.0), N)) * 100.0)
    )
    return outputs


def formula_073_VWMA(ctx: FormulaContext) -> dict[str, Any]:
    """VWMA[ed8cb142baca]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    VOL = ctx.VOL
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    SUM = ctx.SUM
    # Locked parameter defaults.
    N1 = 5.0  # N1
    N2 = 10.0  # N2
    N3 = 50.0  # N3
    N4 = 30.0  # N4
    N5 = 40.0  # N5
    N6 = 60.0  # N6

    # VWMA3
    VWMA3 = (
        (SUM((CLOSE * VOL), N3) / SUM(VOL, N3))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_VWMA_VWMA3
    outputs['wh6_VWMA_VWMA3'] = (
        VWMA3
    )
    return outputs


def formula_074_WAD(ctx: FormulaContext) -> dict[str, Any]:
    """WAD[7fd1f6e4cfe7]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    LOW = ctx.LOW
    HIGH = ctx.HIGH
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    SUM = ctx.SUM
    IFELSE = ctx.IFELSE
    REF = ctx.REF
    MIN = ctx.MIN
    MAX = ctx.MAX

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_WAD_WAD
    outputs['wh6_WAD_WAD'] = (
        SUM(
            IFELSE(
                (CLOSE > REF(CLOSE, 1.0)),
                (CLOSE - MIN(REF(CLOSE, 1.0), LOW)),
                IFELSE((CLOSE < REF(CLOSE, 1.0)), (CLOSE - MAX(REF(CLOSE, 1.0), HIGH)), 0.0),
            ),
            0.0,
        )
    )
    return outputs


def formula_075_WR(ctx: FormulaContext) -> dict[str, Any]:
    """WR[96334a2ee018]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    HIGH = ctx.HIGH
    CLOSE = ctx.CLOSE
    LOW = ctx.LOW
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    HHV = ctx.HHV
    LLV = ctx.LLV
    # Locked parameter defaults.
    N = 14.0  # N

    # WR
    WR = (
        (((-100.0) * (HHV(HIGH, N) - CLOSE)) / (HHV(HIGH, N) - LLV(LOW, N)))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_WR_WR
    outputs['wh6_WR_WR'] = (
        WR
    )
    return outputs


def formula_076_WTD(ctx: FormulaContext) -> dict[str, Any]:
    """WTD[b5dbfb62c033]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    # Locked parameter defaults.
    M = 30.0  # M
    N = 5.0  # N

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_WTD_WTD
    outputs['wh6_WTD_WTD'] = (
        MA(CLOSE, M)
    )
    return outputs


def formula_077_WVAD(ctx: FormulaContext) -> dict[str, Any]:
    """WVAD[4ff241bb0df0]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    OPEN = ctx.OPEN
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    VOL = ctx.VOL

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_WVAD_WVAD
    outputs['wh6_WVAD_WVAD'] = (
        (((CLOSE - OPEN) / (HIGH - LOW)) * VOL)
    )
    return outputs


def formula_078_ZDZB(ctx: FormulaContext) -> dict[str, Any]:
    """ZDZB[46a6e41bad5e]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    COUNT = ctx.COUNT
    REF = ctx.REF
    MA = ctx.MA
    # Locked parameter defaults.
    N1 = 125.0  # N1
    N2 = 5.0  # N2
    N3 = 20.0  # N3

    # A
    A = (
        (COUNT((CLOSE >= REF(CLOSE, 1.0)), N1) / COUNT((CLOSE < REF(CLOSE, 1.0)), N1))
    )

    # B
    B = (
        MA(A, N2)
    )

    # D
    D = (
        MA(A, N3)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_ZDZB_B
    outputs['wh6_ZDZB_B'] = (
        B
    )
    # Explicit locked output: wh6_ZDZB_D
    outputs['wh6_ZDZB_D'] = (
        D
    )
    return outputs


def formula_079_ZLJC(ctx: FormulaContext) -> dict[str, Any]:
    """ZLJC[a37161f969cb]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    LOW = ctx.LOW
    HIGH = ctx.HIGH
    VOL = ctx.VOL
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    SUM = ctx.SUM
    REF = ctx.REF
    EMA = ctx.EMA
    MA = ctx.MA

    # VAR1
    VAR1 = (
        (((CLOSE + LOW) + HIGH) / 3.0)
    )

    # VAR2
    VAR2 = (
        SUM((((((VAR1 - REF(LOW, 1.0)) - (HIGH - VAR1)) * VOL) / 100000.0) / (HIGH - LOW)), 0.0)
    )

    # VAR3
    VAR3 = (
        EMA(VAR2, 1.0)
    )

    # JCL
    JCL = (
        MA(VAR3, 26.0)
    )

    # JCM
    JCM = (
        MA(VAR3, 12.0)
    )

    # JCS
    JCS = (
        VAR3
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_ZLJC_JCL
    outputs['wh6_ZLJC_JCL'] = (
        JCL
    )
    # Explicit locked output: wh6_ZLJC_JCM
    outputs['wh6_ZLJC_JCM'] = (
        JCM
    )
    # Explicit locked output: wh6_ZLJC_JCS
    outputs['wh6_ZLJC_JCS'] = (
        JCS
    )
    return outputs


def formula_080_ZLMM(ctx: FormulaContext) -> dict[str, Any]:
    """ZLMM[a6f4148ed728]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    SMA = ctx.SMA
    MAX = ctx.MAX
    ABS = ctx.ABS
    MA = ctx.MA
    EMA = ctx.EMA

    # LC
    LC = (
        REF(CLOSE, 1.0)
    )

    # RSI3
    RSI3 = (
        ((SMA(MAX((CLOSE - LC), 0.0), 18.0, 1.0) / SMA(ABS((CLOSE - LC)), 18.0, 1.0)) * 100.0)
    )

    # MML
    MML = (
        MA(
            (
                (3.0 * RSI3)
                -
                (((2.0 * SMA(MAX((CLOSE - LC), 0.0), 12.0, 1.0)) / SMA(ABS((CLOSE - LC)), 12.0, 1.0)) * 100.0)
            ),
            5.0,
        )
    )

    # RSI2
    RSI2 = (
        ((SMA(MAX((CLOSE - LC), 0.0), 12.0, 1.0) / SMA(ABS((CLOSE - LC)), 12.0, 1.0)) * 100.0)
    )

    # MMS
    MMS = (
        MA(
            (
                (3.0 * RSI2)
                -
                (((2.0 * SMA(MAX((CLOSE - LC), 0.0), 16.0, 1.0)) / SMA(ABS((CLOSE - LC)), 16.0, 1.0)) * 100.0)
            ),
            3.0,
        )
    )

    # MMM
    MMM = (
        EMA(MMS, 8.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_ZLMM_MML
    outputs['wh6_ZLMM_MML'] = (
        MML
    )
    # Explicit locked output: wh6_ZLMM_MMM
    outputs['wh6_ZLMM_MMM'] = (
        MMM
    )
    # Explicit locked output: wh6_ZLMM_MMS
    outputs['wh6_ZLMM_MMS'] = (
        MMS
    )
    return outputs


def formula_081_Z_SCORE(ctx: FormulaContext) -> dict[str, Any]:
    """Z-SCORE[fa571f2ade8b]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    STD = ctx.STD
    # Locked parameter defaults.
    N = 20.0  # N

    # MA_CLOSE
    MA_CLOSE = (
        MA(CLOSE, N)
    )

    # STD_CLOSE
    STD_CLOSE = (
        STD(CLOSE, N)
    )

    # Z_SCORE
    Z_SCORE = (
        ((CLOSE - MA_CLOSE) / STD_CLOSE)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_Z_SCORE_Z_SCORE
    outputs['wh6_Z_SCORE_Z_SCORE'] = (
        Z_SCORE
    )
    return outputs


def formula_082_indicator(ctx: FormulaContext) -> dict[str, Any]:
    """绘制变色线[8466c64b7dcc]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    C = ctx.C
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA

    # MA1
    MA1 = (
        MA(C, 30.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_u_21e0022b_MA1
    outputs['wh6_u_21e0022b_MA1'] = (
        MA1
    )
    return outputs


def formula_083_indicator(ctx: FormulaContext) -> dict[str, Any]:
    """肯特那[33ef58b48b25]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    # Locked parameter defaults.
    N = 20.0  # N
    M = 10.0  # M
    P = 2.0  # P

    # MID
    MID = (
        MA(CLOSE, N)
    )

    # AAA
    AAA = (
        MA((HIGH - LOW), M)
    )

    # LOWER
    LOWER = (
        (MID - (2.0 * AAA))
    )

    # UPPER
    UPPER = (
        (MID + (2.0 * AAA))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_u_495a23e5_LOWER
    outputs['wh6_u_495a23e5_LOWER'] = (
        LOWER
    )
    # Explicit locked output: wh6_u_495a23e5_MID
    outputs['wh6_u_495a23e5_MID'] = (
        MID
    )
    # Explicit locked output: wh6_u_495a23e5_UPPER
    outputs['wh6_u_495a23e5_UPPER'] = (
        UPPER
    )
    return outputs


def formula_084_indicator(ctx: FormulaContext) -> dict[str, Any]:
    """同时控制颜色和线型[8159389ab834]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    C = ctx.C
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA

    # MA10
    MA10 = (
        MA(C, 10.0)
    )

    # MA30
    MA30 = (
        MA(C, 30.0)
    )

    # MA5
    MA5 = (
        MA(C, 5.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_u_5c41ea6d_MA10
    outputs['wh6_u_5c41ea6d_MA10'] = (
        MA10
    )
    # Explicit locked output: wh6_u_5c41ea6d_MA30
    outputs['wh6_u_5c41ea6d_MA30'] = (
        MA30
    )
    # Explicit locked output: wh6_u_5c41ea6d_MA5
    outputs['wh6_u_5c41ea6d_MA5'] = (
        MA5
    )
    return outputs


def formula_085_indicator(ctx: FormulaContext) -> dict[str, Any]:
    """只显示指标数值不绘制指标线[792497a914a6]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    H = ctx.H
    L = ctx.L
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    HHV = ctx.HHV
    LLV = ctx.LLV

    # H20
    H20 = (
        HHV(H, 20.0)
    )

    # L20
    L20 = (
        LLV(L, 20.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_u_68173cb3_H20
    outputs['wh6_u_68173cb3_H20'] = (
        H20
    )
    # Explicit locked output: wh6_u_68173cb3_L20
    outputs['wh6_u_68173cb3_L20'] = (
        L20
    )
    return outputs


def formula_086_indicator(ctx: FormulaContext) -> dict[str, Any]:
    """唐奇安通道[f662e9c3d070]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    H = ctx.H
    L = ctx.L
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    HHV = ctx.HHV
    LLV = ctx.LLV
    # Locked parameter defaults.
    X1 = 20.0  # X1
    X2 = 20.0  # X2

    # HH
    HH = (
        HHV(H, X1)
    )

    # LL
    LL = (
        LLV(L, X2)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_u_6ae5cc5a_HH
    outputs['wh6_u_6ae5cc5a_HH'] = (
        HH
    )
    # Explicit locked output: wh6_u_6ae5cc5a_LL
    outputs['wh6_u_6ae5cc5a_LL'] = (
        LL
    )
    return outputs


def formula_087_indicator(ctx: FormulaContext) -> dict[str, Any]:
    """绘制虚线[50c0a32c36c8]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    C = ctx.C
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA

    # MA10
    MA10 = (
        MA(C, 10.0)
    )

    # MA5
    MA5 = (
        MA(C, 5.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_u_6f963dfa_MA10
    outputs['wh6_u_6f963dfa_MA10'] = (
        MA10
    )
    # Explicit locked output: wh6_u_6f963dfa_MA5
    outputs['wh6_u_6f963dfa_MA5'] = (
        MA5
    )
    return outputs


def formula_088_indicator(ctx: FormulaContext) -> dict[str, Any]:
    """云端分享示例[9f7e7ed21134]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    C = ctx.C
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA

    # MA15
    MA15 = (
        MA(C, 15.0)
    )

    # MA30
    MA30 = (
        MA(C, 30.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_u_72bedb5a_MA15
    outputs['wh6_u_72bedb5a_MA15'] = (
        MA15
    )
    # Explicit locked output: wh6_u_72bedb5a_MA30
    outputs['wh6_u_72bedb5a_MA30'] = (
        MA30
    )
    return outputs


def formula_089_indicator(ctx: FormulaContext) -> dict[str, Any]:
    """价量运行趋势[8a22479e1a31]: 4 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    VOL = ctx.VOL
    NULL = ctx.NULL
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    REF = ctx.REF
    IF = ctx.IF
    # Locked parameter defaults.
    N = 25.0  # N

    # 价
    价 = (
        MA(CLOSE, N)
    )

    # 量
    量 = (
        MA(VOL, N)
    )

    # DT
    DT = (
        ctx.logical_and((价 > REF(价, 1.0)), (量 > REF(量, 1.0)))
    )

    # DT1
    DT1 = (
        IF(DT, 价, NULL)
    )

    # KT
    KT = (
        ctx.logical_and((价 < REF(价, 1.0)), (量 < REF(量, 1.0)))
    )

    # KT1
    KT1 = (
        IF(KT, 价, NULL)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_u_78c25b4e_DT1
    outputs['wh6_u_78c25b4e_DT1'] = (
        DT1
    )
    # Explicit locked output: wh6_u_78c25b4e_KT1
    outputs['wh6_u_78c25b4e_KT1'] = (
        KT1
    )
    # Explicit locked output: wh6_u_78c25b4e_u_273a581d
    outputs['wh6_u_78c25b4e_u_273a581d'] = (
        价
    )
    # Explicit locked output: wh6_u_78c25b4e_u_2da16149
    outputs['wh6_u_78c25b4e_u_2da16149'] = (
        量
    )
    return outputs


def formula_090_indicator(ctx: FormulaContext) -> dict[str, Any]:
    """布林带带宽[98fab1768439]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    STD = ctx.STD
    IF = ctx.IF
    # Locked parameter defaults.
    N = 20.0  # N
    K = 2.0  # K

    # MB
    MB = (
        MA(CLOSE, N)
    )

    # SD
    SD = (
        STD(CLOSE, N)
    )

    # UB
    UB = (
        (MB + (K * SD))
    )

    # LB
    LB = (
        (MB - (K * SD))
    )

    # BBW
    BBW = (
        IF((MB == 0.0), 0.0, ((UB - LB) / MB))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_u_8b96f436_BBW
    outputs['wh6_u_8b96f436_BBW'] = (
        BBW
    )
    return outputs


def formula_091_indicator(ctx: FormulaContext) -> dict[str, Any]:
    """绘制小圆点线[2addbe3bad45]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    C = ctx.C
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA

    # MA10
    MA10 = (
        MA(C, 10.0)
    )

    # MA30
    MA30 = (
        MA(C, 30.0)
    )

    # MA5
    MA5 = (
        MA(C, 5.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_u_9a0c2be9_MA10
    outputs['wh6_u_9a0c2be9_MA10'] = (
        MA10
    )
    # Explicit locked output: wh6_u_9a0c2be9_MA30
    outputs['wh6_u_9a0c2be9_MA30'] = (
        MA30
    )
    # Explicit locked output: wh6_u_9a0c2be9_MA5
    outputs['wh6_u_9a0c2be9_MA5'] = (
        MA5
    )
    return outputs


def formula_092_indicator(ctx: FormulaContext) -> dict[str, Any]:
    """道奇安通道[442bb8b47357]: 3 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    LOW = ctx.LOW
    HIGH = ctx.HIGH
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    LLV = ctx.LLV
    HHV = ctx.HHV
    # Locked parameter defaults.
    N = 20.0  # N

    # LOWER
    LOWER = (
        LLV(LOW, N)
    )

    # UPPER
    UPPER = (
        HHV(HIGH, N)
    )

    # MIDDLE
    MIDDLE = (
        ((UPPER + LOWER) / 2.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_u_a4f8ae15_LOWER
    outputs['wh6_u_a4f8ae15_LOWER'] = (
        LOWER
    )
    # Explicit locked output: wh6_u_a4f8ae15_MIDDLE
    outputs['wh6_u_a4f8ae15_MIDDLE'] = (
        MIDDLE
    )
    # Explicit locked output: wh6_u_a4f8ae15_UPPER
    outputs['wh6_u_a4f8ae15_UPPER'] = (
        UPPER
    )
    return outputs


def formula_093_indicator(ctx: FormulaContext) -> dict[str, Any]:
    """四合一指标[7c414e14527e]: 4 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    REF = ctx.REF
    SMA = ctx.SMA
    MAX = ctx.MAX
    ABS = ctx.ABS
    MA = ctx.MA
    AVEDEV = ctx.AVEDEV
    MIN = ctx.MIN
    # Locked parameter defaults.
    N = 7.0  # N
    P = 24.0  # P
    M = 20.0  # M
    L2 = 12.0  # L2
    E = 14.0  # E

    # LC
    LC = (
        REF(CLOSE, 1.0)
    )

    # RSI
    RSI = (
        ((SMA(MAX((CLOSE - LC), 0.0), N, 1.0) / SMA(ABS((CLOSE - LC)), N, 1.0)) * 100.0)
    )

    # RSI_N
    RSI_N = (
        ((RSI - 50.0) / 50.0)
    )

    # BIAS2
    BIAS2 = (
        (((CLOSE - MA(CLOSE, L2)) / MA(CLOSE, L2)) * 100.0)
    )

    # BIAS_N
    BIAS_N = (
        (BIAS2 / (ABS(BIAS2) + 2.0))
    )

    # ROC
    ROC = (
        (((CLOSE - REF(CLOSE, P)) / REF(CLOSE, P)) * 100.0)
    )

    # ROC_N
    ROC_N = (
        (ROC / (ABS(ROC) + 2.0))
    )

    # TP
    TP = (
        (((HIGH + LOW) + CLOSE) / 3.0)
    )

    # CCI
    CCI = (
        ((TP - MA(TP, E)) / (0.015 * AVEDEV(TP, E)))
    )

    # CCI_S
    CCI_S = (
        (CCI / 100.0)
    )

    # CCI_N
    CCI_N = (
        (CCI_S / (ABS(CCI_S) + 1.0))
    )

    # MULTI_RAW
    MULTI_RAW = (
        ((((0.0 * RSI_N) + (0.0 * BIAS_N)) + (1.0 * ROC_N)) + (0.0 * CCI_N))
    )

    # MULTI_VAL
    MULTI_VAL = (
        ((MULTI_RAW + 1.0) * 50.0)
    )

    # MULTI_CLIP
    MULTI_CLIP = (
        MAX(MIN(MULTI_VAL, 100.0), 0.0)
    )

    # MULTI
    MULTI = (
        MULTI_CLIP
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_u_a8b37c90_MULTI
    outputs['wh6_u_a8b37c90_MULTI'] = (
        MULTI
    )
    # Explicit locked output: wh6_u_a8b37c90_u_a8b37c90
    outputs['wh6_u_a8b37c90_u_a8b37c90'] = (
        50.0
    )
    # Explicit locked output: wh6_u_a8b37c90_u_a8b37c90_2
    outputs['wh6_u_a8b37c90_u_a8b37c90_2'] = (
        79.0
    )
    # Explicit locked output: wh6_u_a8b37c90_u_a8b37c90_3
    outputs['wh6_u_a8b37c90_u_a8b37c90_3'] = (
        21.0
    )
    return outputs


def formula_094_indicator(ctx: FormulaContext) -> dict[str, Any]:
    """闪电图[7adb49cbf30e]: 2 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MA = ctx.MA
    # Locked parameter defaults.
    N = 60.0  # N

    # MA1
    MA1 = (
        MA(CLOSE, N)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_u_d6d18ecd_MA1
    outputs['wh6_u_d6d18ecd_MA1'] = (
        MA1
    )
    # Explicit locked output: wh6_u_d6d18ecd_u_d6d18ecd
    outputs['wh6_u_d6d18ecd_u_d6d18ecd'] = (
        CLOSE
    )
    return outputs


def formula_095_indicator(ctx: FormulaContext) -> dict[str, Any]:
    """终极振荡器[b14d7d27233f]: 1 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    CLOSE = ctx.CLOSE
    LOW = ctx.LOW
    HIGH = ctx.HIGH
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MIN = ctx.MIN
    REF = ctx.REF
    MAX = ctx.MAX
    SUM = ctx.SUM

    # BPVAL
    BPVAL = (
        (CLOSE - MIN(LOW, REF(CLOSE, 1.0)))
    )

    # N1
    N1 = (
        7.0
    )

    # TRVAL
    TRVAL = (
        (MAX(HIGH, REF(CLOSE, 1.0)) - MIN(LOW, REF(CLOSE, 1.0)))
    )

    # AVG1
    AVG1 = (
        (SUM(BPVAL, N1) / SUM(TRVAL, N1))
    )

    # N2
    N2 = (
        14.0
    )

    # AVG2
    AVG2 = (
        (SUM(BPVAL, N2) / SUM(TRVAL, N2))
    )

    # N3
    N3 = (
        28.0
    )

    # AVG3
    AVG3 = (
        (SUM(BPVAL, N3) / SUM(TRVAL, N3))
    )

    # UO
    UO = (
        ((100.0 * (((4.0 * AVG1) + (2.0 * AVG2)) + AVG3)) / 7.0)
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_u_dc9bfffe_UO
    outputs['wh6_u_dc9bfffe_UO'] = (
        UO
    )
    return outputs


def formula_096_indicator(ctx: FormulaContext) -> dict[str, Any]:
    """论文策略[9cb69af149e2]: 5 locked output(s)."""
    # Market fields and locked aliases used by this formula.
    HIGH = ctx.HIGH
    LOW = ctx.LOW
    CLOSE = ctx.CLOSE
    # Audited WH6 primitives; arithmetic/comparisons remain native Python.
    MAX = ctx.MAX
    ABS = ctx.ABS
    REF = ctx.REF
    MA = ctx.MA
    EMA = ctx.EMA
    # Locked parameter defaults.
    N = 20.0  # N
    M = 10.0  # M
    K = 1.0  # K

    # TR
    TR = (
        MAX(MAX((HIGH - LOW), ABS((REF(CLOSE, 1.0) - HIGH))), ABS((REF(CLOSE, 1.0) - LOW)))
    )

    # AAA
    AAA = (
        MA(TR, M)
    )

    # MID
    MID = (
        EMA(CLOSE, N)
    )

    # LOWER
    LOWER = (
        (MID - (1.5 * AAA))
    )

    # UPPER
    UPPER = (
        (MID + (1.5 * AAA))
    )

    outputs: dict[str, Any] = {}
    # Explicit locked output: wh6_u_dcb52af4_AAA
    outputs['wh6_u_dcb52af4_AAA'] = (
        AAA
    )
    # Explicit locked output: wh6_u_dcb52af4_LOWER
    outputs['wh6_u_dcb52af4_LOWER'] = (
        LOWER
    )
    # Explicit locked output: wh6_u_dcb52af4_MID
    outputs['wh6_u_dcb52af4_MID'] = (
        MID
    )
    # Explicit locked output: wh6_u_dcb52af4_TR
    outputs['wh6_u_dcb52af4_TR'] = (
        TR
    )
    # Explicit locked output: wh6_u_dcb52af4_UPPER
    outputs['wh6_u_dcb52af4_UPPER'] = (
        UPPER
    )
    return outputs


FORMULA_GROUPS = (
    formula_000_ADTM,
    formula_001_AD,
    formula_002_ARBR,
    formula_003_ASI,
    formula_004_ATR,
    formula_005_B3612,
    formula_006_BAR,
    formula_007_BBIBOLL,
    formula_008_BBI,
    formula_009_BIAS,
    formula_010_BOLL,
    formula_011_CCI,
    formula_012_CCL,
    formula_013_CDP,
    formula_014_CJL,
    formula_015_CLOSE,
    formula_016_CR,
    formula_017_DBCD,
    formula_018_DDI,
    formula_019_DEMA,
    formula_020_DKX,
    formula_021_DMA,
    formula_022_DMI,
    formula_023_DPO,
    formula_024_EMA2,
    formula_025_EMA,
    formula_026_ENV,
    formula_027_FIBONACCI_BANDS,
    formula_028_HCL,
    formula_029_HIGH,
    formula_030_KDJ,
    formula_031_KD,
    formula_032_LON,
    formula_033_LOW,
    formula_034_MACD,
    formula_035_MASS,
    formula_036_MA,
    formula_037_MFI,
    formula_038_MFI,
    formula_039_MICD,
    formula_040_MIKE,
    formula_041_MI,
    formula_042_MTM,
    formula_043_MV,
    formula_044_MYFORCAST,
    formula_045_OBV,
    formula_046_OPEN,
    formula_047_PRICEOSC,
    formula_048_PSY,
    formula_049_PUBU,
    formula_050_PVT,
    formula_051_QHLSR,
    formula_052_RCCD,
    formula_053_RC,
    formula_054_ROC,
    formula_055_ROC,
    formula_056_RSIS,
    formula_057_RSI,
    formula_058_RSI_WILDER,
    formula_059_SAR1,
    formula_060_SAR,
    formula_061_SHORT,
    formula_062_SLOWKD,
    formula_063_SMA,
    formula_064_SP,
    formula_065_SRDM,
    formula_066_SRMI,
    formula_067_STOCHASTIC_RSI,
    formula_068_VOLATILITY,
    formula_069_VOSC,
    formula_070_VROC,
    formula_071_VRSI,
    formula_072_VR,
    formula_073_VWMA,
    formula_074_WAD,
    formula_075_WR,
    formula_076_WTD,
    formula_077_WVAD,
    formula_078_ZDZB,
    formula_079_ZLJC,
    formula_080_ZLMM,
    formula_081_Z_SCORE,
    formula_082_indicator,
    formula_083_indicator,
    formula_084_indicator,
    formula_085_indicator,
    formula_086_indicator,
    formula_087_indicator,
    formula_088_indicator,
    formula_089_indicator,
    formula_090_indicator,
    formula_091_indicator,
    formula_092_indicator,
    formula_093_indicator,
    formula_094_indicator,
    formula_095_indicator,
    formula_096_indicator,
)

FORMULA_GROUP_METADATA = (
    ('formula_000_ADTM', 'ADTM[6afdf7a14e11]', ('wh6_ADTM_ADTM', 'wh6_ADTM_ADTMMA')),
    ('formula_001_AD', 'AD[1c547921b117]', ('wh6_AD_AD',)),
    ('formula_002_ARBR', 'ARBR[6b716a7bb085]', ('wh6_ARBR_AR', 'wh6_ARBR_BR')),
    ('formula_003_ASI', 'ASI[587a9d384c4d]', ('wh6_ASI_ASI',)),
    ('formula_004_ATR', 'ATR[7e971724d411]', ('wh6_ATR_ATR', 'wh6_ATR_TR')),
    ('formula_005_B3612', 'B3612[85515d05832b]', ('wh6_B3612_B36', 'wh6_B3612_B612')),
    ('formula_006_BAR', 'BAR[25d163f925dd]', ('wh6_BAR_BAR',)),
    ('formula_007_BBIBOLL', 'BBIBOLL[cc1c9a4cec06]', ('wh6_BBIBOLL_BBIBOLL', 'wh6_BBIBOLL_DWN', 'wh6_BBIBOLL_UPR')),
    ('formula_008_BBI', 'BBI[b585b99484ed]', ('wh6_BBI_BBI',)),
    ('formula_009_BIAS', 'BIAS[c3c570961585]', ('wh6_BIAS_BIAS1', 'wh6_BIAS_BIAS2', 'wh6_BIAS_BIAS3')),
    ('formula_010_BOLL', 'BOLL[78b8e217a7f5]', ('wh6_BOLL_BOTTOM', 'wh6_BOLL_MID', 'wh6_BOLL_TOP')),
    ('formula_011_CCI', 'CCI[3fc4dc01571c]', ('wh6_CCI_CCI',)),
    ('formula_012_CCL', 'CCL[6c88ce571d6a]', ('wh6_CCL_CCL',)),
    ('formula_013_CDP', 'CDP[46525abce43d]', ('wh6_CDP_AH', 'wh6_CDP_AL', 'wh6_CDP_CDP', 'wh6_CDP_NH', 'wh6_CDP_NL')),
    ('formula_014_CJL', 'CJL[3977d607f195]', ('wh6_CJL_CJL',)),
    ('formula_015_CLOSE', 'CLOSE[685de8bb54b6]', ('wh6_CLOSE_CLOSE',)),
    ('formula_016_CR', 'CR[480d4993d264]', ('wh6_CR_CR', 'wh6_CR_CRMA1', 'wh6_CR_CRMA2', 'wh6_CR_CRMA3', 'wh6_CR_CRMA4')),
    ('formula_017_DBCD', 'DBCD[c836761df84b]', ('wh6_DBCD_DBCD', 'wh6_DBCD_MM')),
    ('formula_018_DDI', 'DDI[745da764bac5]', ('wh6_DDI_AD', 'wh6_DDI_ADDI', 'wh6_DDI_DDI')),
    ('formula_019_DEMA', 'DEMA[1768501f582e]', ('wh6_DEMA_DEMA',)),
    ('formula_020_DKX', 'DKX[72aff29ad6a0]', ('wh6_DKX_B', 'wh6_DKX_D')),
    ('formula_021_DMA', 'DMA[7a6e2e16b102]', ('wh6_DMA_AMA', 'wh6_DMA_DDD')),
    ('formula_022_DMI', 'DMI[4d958bb33736]', ('wh6_DMI_ADX', 'wh6_DMI_ADXR', 'wh6_DMI_MDI', 'wh6_DMI_PDI')),
    ('formula_023_DPO', 'DPO[687a5b927b4c]', ('wh6_DPO_DPO',)),
    ('formula_024_EMA2', 'EMA2[4da7fae9d327]', ('wh6_EMA2_MA1',)),
    ('formula_025_EMA', 'EMA[067f3c40e24b]', ('wh6_EMA_MA1',)),
    ('formula_026_ENV', 'ENV[999d9e148aed]', ('wh6_ENV_LOWER', 'wh6_ENV_UPPER')),
    ('formula_027_FIBONACCI_BANDS', 'FIBONACCI BANDS[95dd251e2618]', ('wh6_FIBONACCI_BANDS_FIBONACCI_BANDS', 'wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_2', 'wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_3', 'wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_4', 'wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_5', 'wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_6', 'wh6_FIBONACCI_BANDS_FIBONACCI_BANDS_7')),
    ('formula_028_HCL', 'HCL[94addf722c9d]', ('wh6_HCL_MAC', 'wh6_HCL_MAH', 'wh6_HCL_MAL')),
    ('formula_029_HIGH', 'HIGH[4a5b7a67f44a]', ('wh6_HIGH_HIGH',)),
    ('formula_030_KDJ', 'KDJ[2693ba61e79f]', ('wh6_KDJ_D', 'wh6_KDJ_J', 'wh6_KDJ_K')),
    ('formula_031_KD', 'KD[1b3caa4bed83]', ('wh6_KD_D', 'wh6_KD_K')),
    ('formula_032_LON', 'LON长线[fe0f90cc8208]', ('wh6_LON_LON', 'wh6_LON_LONGMA', 'wh6_LON_LONGT')),
    ('formula_033_LOW', 'LOW[2e2429934f1e]', ('wh6_LOW_LOW',)),
    ('formula_034_MACD', 'MACD[8ec10f3b6154]', ('wh6_MACD_DEA', 'wh6_MACD_DIFF', 'wh6_MACD_MACD')),
    ('formula_035_MASS', 'MASS[ee67c0f903d7]', ('wh6_MASS_MASS',)),
    ('formula_036_MA', 'MA[070288e4d7c8]', ('wh6_MA_MA1',)),
    ('formula_037_MFI', 'MFI[bfc4218bf782]', ('wh6_MFI_MFI',)),
    ('formula_038_MFI', '资金流量MFI[d54cecd8882f]', ('wh6_MFI_MFI_2',)),
    ('formula_039_MICD', 'MICD[c6480329fe65]', ('wh6_MICD_DIF', 'wh6_MICD_MICD')),
    ('formula_040_MIKE', 'MIKE[e35a26cbc933]', ('wh6_MIKE_MR', 'wh6_MIKE_MS', 'wh6_MIKE_SR', 'wh6_MIKE_SS', 'wh6_MIKE_WR', 'wh6_MIKE_WS')),
    ('formula_041_MI', 'MI[d43023fd036d]', ('wh6_MI_A', 'wh6_MI_MI')),
    ('formula_042_MTM', 'MTM[b2ed05216bb0]', ('wh6_MTM_MTM', 'wh6_MTM_MTMMA')),
    ('formula_043_MV', 'MV[a1fbc33a6fac]', ('wh6_MV_MV', 'wh6_MV_MV_2', 'wh6_MV_MV_3')),
    ('formula_044_MYFORCAST', 'MYFORCAST[03b05cf478b3]', ('wh6_MYFORCAST_MYFORCAST',)),
    ('formula_045_OBV', 'OBV[2ba4cc6f407d]', ('wh6_OBV_OBV', 'wh6_OBV_OBVMA')),
    ('formula_046_OPEN', 'OPEN[32f0bacd5e2f]', ('wh6_OPEN_OPEN',)),
    ('formula_047_PRICEOSC', 'PRICEOSC[83cd869938cf]', ('wh6_PRICEOSC_PRICEOSC',)),
    ('formula_048_PSY', 'PSY[cdf8c42ae903]', ('wh6_PSY_PSY', 'wh6_PSY_PSYMA')),
    ('formula_049_PUBU', 'PUBU[79271ae789a6]', ('wh6_PUBU_PB1', 'wh6_PUBU_PB2', 'wh6_PUBU_PB3', 'wh6_PUBU_PB4', 'wh6_PUBU_PB5', 'wh6_PUBU_PB6')),
    ('formula_050_PVT', 'PVT[5004435db5f8]', ('wh6_PVT_PVT',)),
    ('formula_051_QHLSR', 'QHLSR[42615538a4be]', ('wh6_QHLSR_QHL10', 'wh6_QHLSR_QHL5')),
    ('formula_052_RCCD', 'RCCD[781a794ee92d]', ('wh6_RCCD_DIF', 'wh6_RCCD_RCCD')),
    ('formula_053_RC', 'RC[41f33d69be01]', ('wh6_RC_ARC',)),
    ('formula_054_ROC', 'ROC[1f4d053ed38c]', ('wh6_ROC_ROC', 'wh6_ROC_ROCMA')),
    ('formula_055_ROC', 'ROC有界限版[61284b24cb4c]', ('wh6_ROC_ROCMA_2', 'wh6_ROC_ROC_2', 'wh6_ROC_ROC_B')),
    ('formula_056_RSIS', 'RSIS[044808e77e15]', ('wh6_RSIS_RSIS1', 'wh6_RSIS_RSIS2')),
    ('formula_057_RSI', 'RSI[7c1ddc0b3faa]', ('wh6_RSI_RSI1', 'wh6_RSI_RSI2')),
    ('formula_058_RSI_WILDER', 'RSI_WILDER[96e490f3b509]', ('wh6_RSI_WILDER_RSI1', 'wh6_RSI_WILDER_RSI2')),
    ('formula_059_SAR1', 'SAR1[5e35acba7fa0]', ('wh6_SAR1_SARLINE',)),
    ('formula_060_SAR', 'SAR[699677c4dbee]', ('wh6_SAR_SARLINE',)),
    ('formula_061_SHORT', 'SHORT短线[c908591ee874]', ('wh6_SHORT_SHORT', 'wh6_SHORT_SHORTMA', 'wh6_SHORT_SHORTT')),
    ('formula_062_SLOWKD', 'SLOWKD[73ec6bbc6f5d]', ('wh6_SLOWKD_D', 'wh6_SLOWKD_K')),
    ('formula_063_SMA', 'SMA[cd85e36bfc6e]', ('wh6_SMA_SMA',)),
    ('formula_064_SP', 'SP[5922aa5dbc05]', ('wh6_SP_SP',)),
    ('formula_065_SRDM', 'SRDM[56994753572a]', ('wh6_SRDM_ASRDM', 'wh6_SRDM_SRDM')),
    ('formula_066_SRMI', 'SRMI[cb604fa33bae]', ('wh6_SRMI_SRMI',)),
    ('formula_067_STOCHASTIC_RSI', 'STOCHASTIC RSI[977acef3e03a]', ('wh6_STOCHASTIC_RSI_RSI_BASE', 'wh6_STOCHASTIC_RSI_STOCH_RSI_RAW')),
    ('formula_068_VOLATILITY', 'VOLATILITY[12805f344569]', ('wh6_VOLATILITY_u_c40446c0',)),
    ('formula_069_VOSC', 'VOSC[e4af5638db70]', ('wh6_VOSC_OBVMA', 'wh6_VOSC_VOSC')),
    ('formula_070_VROC', 'VROC[b1d6fae4c713]', ('wh6_VROC_VROC',)),
    ('formula_071_VRSI', 'VRSI[2a4be8ff07d3]', ('wh6_VRSI_VRSI',)),
    ('formula_072_VR', 'VR[ecda4391a2c2]', ('wh6_VR_VR',)),
    ('formula_073_VWMA', 'VWMA[ed8cb142baca]', ('wh6_VWMA_VWMA3',)),
    ('formula_074_WAD', 'WAD[7fd1f6e4cfe7]', ('wh6_WAD_WAD',)),
    ('formula_075_WR', 'WR[96334a2ee018]', ('wh6_WR_WR',)),
    ('formula_076_WTD', 'WTD[b5dbfb62c033]', ('wh6_WTD_WTD',)),
    ('formula_077_WVAD', 'WVAD[4ff241bb0df0]', ('wh6_WVAD_WVAD',)),
    ('formula_078_ZDZB', 'ZDZB[46a6e41bad5e]', ('wh6_ZDZB_B', 'wh6_ZDZB_D')),
    ('formula_079_ZLJC', 'ZLJC[a37161f969cb]', ('wh6_ZLJC_JCL', 'wh6_ZLJC_JCM', 'wh6_ZLJC_JCS')),
    ('formula_080_ZLMM', 'ZLMM[a6f4148ed728]', ('wh6_ZLMM_MML', 'wh6_ZLMM_MMM', 'wh6_ZLMM_MMS')),
    ('formula_081_Z_SCORE', 'Z-SCORE[fa571f2ade8b]', ('wh6_Z_SCORE_Z_SCORE',)),
    ('formula_082_indicator', '绘制变色线[8466c64b7dcc]', ('wh6_u_21e0022b_MA1',)),
    ('formula_083_indicator', '肯特那[33ef58b48b25]', ('wh6_u_495a23e5_LOWER', 'wh6_u_495a23e5_MID', 'wh6_u_495a23e5_UPPER')),
    ('formula_084_indicator', '同时控制颜色和线型[8159389ab834]', ('wh6_u_5c41ea6d_MA10', 'wh6_u_5c41ea6d_MA30', 'wh6_u_5c41ea6d_MA5')),
    ('formula_085_indicator', '只显示指标数值不绘制指标线[792497a914a6]', ('wh6_u_68173cb3_H20', 'wh6_u_68173cb3_L20')),
    ('formula_086_indicator', '唐奇安通道[f662e9c3d070]', ('wh6_u_6ae5cc5a_HH', 'wh6_u_6ae5cc5a_LL')),
    ('formula_087_indicator', '绘制虚线[50c0a32c36c8]', ('wh6_u_6f963dfa_MA10', 'wh6_u_6f963dfa_MA5')),
    ('formula_088_indicator', '云端分享示例[9f7e7ed21134]', ('wh6_u_72bedb5a_MA15', 'wh6_u_72bedb5a_MA30')),
    ('formula_089_indicator', '价量运行趋势[8a22479e1a31]', ('wh6_u_78c25b4e_DT1', 'wh6_u_78c25b4e_KT1', 'wh6_u_78c25b4e_u_273a581d', 'wh6_u_78c25b4e_u_2da16149')),
    ('formula_090_indicator', '布林带带宽[98fab1768439]', ('wh6_u_8b96f436_BBW',)),
    ('formula_091_indicator', '绘制小圆点线[2addbe3bad45]', ('wh6_u_9a0c2be9_MA10', 'wh6_u_9a0c2be9_MA30', 'wh6_u_9a0c2be9_MA5')),
    ('formula_092_indicator', '道奇安通道[442bb8b47357]', ('wh6_u_a4f8ae15_LOWER', 'wh6_u_a4f8ae15_MIDDLE', 'wh6_u_a4f8ae15_UPPER')),
    ('formula_093_indicator', '四合一指标[7c414e14527e]', ('wh6_u_a8b37c90_MULTI', 'wh6_u_a8b37c90_u_a8b37c90', 'wh6_u_a8b37c90_u_a8b37c90_2', 'wh6_u_a8b37c90_u_a8b37c90_3')),
    ('formula_094_indicator', '闪电图[7adb49cbf30e]', ('wh6_u_d6d18ecd_MA1', 'wh6_u_d6d18ecd_u_d6d18ecd')),
    ('formula_095_indicator', '终极振荡器[b14d7d27233f]', ('wh6_u_dc9bfffe_UO',)),
    ('formula_096_indicator', '论文策略[9cb69af149e2]', ('wh6_u_dcb52af4_AAA', 'wh6_u_dcb52af4_LOWER', 'wh6_u_dcb52af4_MID', 'wh6_u_dcb52af4_TR', 'wh6_u_dcb52af4_UPPER')),
)
