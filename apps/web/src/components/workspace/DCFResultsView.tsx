import type { ValuationResult } from '../../lib/api'
import { TrendingUp, BarChart3, Target, Shield, Activity } from 'lucide-react'

interface Props { data: ValuationResult }

function fmt(n: number | undefined, decimals = 0): string {
    if (n === undefined || n === null) return '—'
    if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(1)}B`
    if (Math.abs(n) >= 1e7) return `${(n / 1e7).toFixed(1)} Cr`
    if (Math.abs(n) >= 1e5) return `${(n / 1e5).toFixed(1)}L`
    return n.toLocaleString('en-IN', { maximumFractionDigits: decimals })
}

function pct(n: number | undefined): string {
    if (n === undefined || n === null) return '—'
    return `${(n * 100).toFixed(1)}%`
}

function currency(n: number | undefined, cur = '₹'): string {
    if (n === undefined || n === null) return '—'
    return `${cur}${fmt(n, 2)}`
}

export default function DCFResultsView({ data }: Props) {
    const h = data.header
    const cur = h.currency === 'USD' ? '$' : '₹'

    return (
        <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* ── Hero ── */}
            <div style={{
                background: '#0a0a0a', border: '1px solid #222', borderRadius: 3,
                padding: '20px 24px'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                    <TrendingUp size={16} style={{ color: '#ff6600' }} />
                    <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.04em' }}>DCF VALUATION</span>
                    <span className="badge badge-emerald" style={{ marginLeft: 'auto' }}>COMPLETED</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 0, border: '1px solid #1a1a1a', borderRadius: 2, overflow: 'hidden' }}>
                    {[
                        { label: 'ENTERPRISE VALUE', value: currency(h.enterprise_value, cur) },
                        { label: 'EQUITY VALUE', value: currency(h.equity_value, cur) },
                        { label: 'SHARE PRICE', value: `${cur}${h.implied_share_price?.toFixed(2)}`, highlight: true },
                        { label: 'WACC', value: pct(h.wacc) },
                        { label: 'TV METHOD', value: h.terminal_method || 'Gordon' },
                    ].map((m, i) => (
                        <div key={i} style={{
                            textAlign: 'center', padding: '14px 10px',
                            borderRight: i < 4 ? '1px solid #1a1a1a' : 'none',
                            background: m.highlight ? 'rgba(255,102,0,0.04)' : 'transparent'
                        }}>
                            <div style={{ fontSize: 9, color: '#555', letterSpacing: '0.1em', fontWeight: 700, marginBottom: 6 }}>{m.label}</div>
                            <div style={{
                                fontSize: m.highlight ? 22 : 16, fontWeight: 700,
                                color: m.highlight ? '#ff6600' : '#fff',
                                fontFamily: "'SF Mono', Consolas, monospace"
                            }}>{m.value}</div>
                        </div>
                    ))}
                </div>
            </div>

            {/* ── Scenarios ── */}
            {data.scenarios && (
                <div style={{ background: '#0a0a0a', border: '1px solid #222', borderRadius: 3 }}>
                    <div style={{ padding: '10px 20px', borderBottom: '1px solid #222', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <BarChart3 size={13} style={{ color: '#3399ff' }} />
                        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: '#aaa' }}>SCENARIO ANALYSIS</span>
                    </div>
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Scenario</th>
                                <th>Rev CAGR</th>
                                <th>EBITDA Mgn</th>
                                <th>EV</th>
                                <th>Equity</th>
                                <th>Share Price</th>
                            </tr>
                        </thead>
                        <tbody>
                            {(['bear', 'base', 'bull'] as const).map(key => {
                                const s = data.scenarios![key]
                                const colors: Record<string, string> = { bear: '#cc3333', base: '#fff', bull: '#00cc66' }
                                return (
                                    <tr key={key}>
                                        <td style={{ fontWeight: 700, color: colors[key], fontFamily: "'Inter', system-ui, sans-serif" }}>{s.label}</td>
                                        <td>{pct(s.revenue_cagr)}</td>
                                        <td>{pct(s.ebitda_margin)}</td>
                                        <td>{currency(s.valuation?.enterprise_value, cur)}</td>
                                        <td>{currency(s.valuation?.equity_value, cur)}</td>
                                        <td style={{ fontWeight: 700, color: colors[key] }}>
                                            {cur}{s.valuation?.share_price?.toFixed(2)}
                                        </td>
                                    </tr>
                                )
                            })}
                        </tbody>
                    </table>
                </div>
            )}

            {/* ── EV Bridge ── */}
            {data.ev_bridge && (
                <div style={{ background: '#0a0a0a', border: '1px solid #222', borderRadius: 3 }}>
                    <div style={{ padding: '10px 20px', borderBottom: '1px solid #222', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Target size={13} style={{ color: '#3399ff' }} />
                        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: '#aaa' }}>EV TO EQUITY BRIDGE</span>
                    </div>
                    <div style={{ padding: '4px 0' }}>
                        {Object.entries(data.ev_bridge).map(([label, value]) => (
                            <div key={label} style={{
                                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                padding: '8px 20px', borderBottom: '1px solid #111'
                            }}>
                                <span style={{ fontSize: 12, color: '#888', fontFamily: "'Inter', system-ui, sans-serif" }}>
                                    {label.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                                </span>
                                <span style={{
                                    fontSize: 13, fontWeight: 600, fontFamily: "'SF Mono', Consolas, monospace",
                                    color: typeof value === 'number' && value < 0 ? '#cc3333' : '#fff'
                                }}>
                                    {currency(value as number, cur)}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* ── TV Cross-Check ── */}
            {data.tv_crosscheck && (
                <div style={{ background: '#0a0a0a', border: '1px solid #222', borderRadius: 3 }}>
                    <div style={{ padding: '10px 20px', borderBottom: '1px solid #222', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Shield size={13} style={{ color: '#ffaa00' }} />
                        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: '#aaa' }}>TV CROSS-CHECK</span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Object.keys(data.tv_crosscheck).length}, 1fr)`, gap: 0 }}>
                        {Object.entries(data.tv_crosscheck).map(([label, value], i, arr) => (
                            <div key={label} style={{
                                textAlign: 'center', padding: '14px 10px',
                                borderRight: i < arr.length - 1 ? '1px solid #1a1a1a' : 'none'
                            }}>
                                <div style={{ fontSize: 9, color: '#555', letterSpacing: '0.1em', fontWeight: 700, marginBottom: 6 }}>
                                    {label.replace(/_/g, ' ').toUpperCase()}
                                </div>
                                <div style={{ fontSize: 14, fontWeight: 700, color: '#fff', fontFamily: "'SF Mono', Consolas, monospace" }}>
                                    {typeof value === 'number' ? currency(value, cur) : String(value)}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* ── Sensitivity ── */}
            {data.sensitivity_wacc_tgr && data.sensitivity_labels && (
                <div style={{ background: '#0a0a0a', border: '1px solid #222', borderRadius: 3 }}>
                    <div style={{ padding: '10px 20px', borderBottom: '1px solid #222', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Activity size={13} style={{ color: '#00cc66' }} />
                        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: '#aaa' }}>WACC × TGR SENSITIVITY</span>
                    </div>
                    <div style={{ overflowX: 'auto' }}>
                        <table className="data-table" style={{ minWidth: 500 }}>
                            <thead>
                                <tr>
                                    <th style={{ fontSize: 9 }}>WACC \ TGR</th>
                                    {data.sensitivity_labels.tgr.map(t => (
                                        <th key={t} style={{ textAlign: 'center' }}>{pct(t)}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {data.sensitivity_wacc_tgr.map((row, wi) => (
                                    <tr key={wi}>
                                        <td style={{ fontWeight: 700, color: '#fff' }}>
                                            {pct(data.sensitivity_labels!.wacc[wi])}
                                        </td>
                                        {row.map((val, ti) => {
                                            const isBase = wi === Math.floor(data.sensitivity_wacc_tgr!.length / 2) && ti === Math.floor(row.length / 2)
                                            return (
                                                <td key={ti} style={{
                                                    textAlign: 'center', fontWeight: isBase ? 700 : 400,
                                                    color: isBase ? '#ff6600' : '#999',
                                                    background: isBase ? 'rgba(255,102,0,0.06)' : 'transparent',
                                                }}>
                                                    {cur}{typeof val === 'number' ? val.toFixed(2) : val}
                                                </td>
                                            )
                                        })}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* ── Extraction Metadata ── */}
            {data.extraction_metadata && (
                <div style={{ background: '#0a0a0a', border: '1px solid #222', borderRadius: 3, padding: '12px 20px' }}>
                    <span style={{ fontSize: 10, color: '#555', fontWeight: 700, letterSpacing: '0.08em' }}>EXTRACTION</span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginTop: 8 }}>
                        {Object.entries(data.extraction_metadata).map(([key, value]) => (
                            <div key={key} style={{ fontSize: 11, color: '#666' }}>
                                <span style={{ color: '#888' }}>{key.replace(/_/g, ' ')}: </span>
                                {String(value)}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}
