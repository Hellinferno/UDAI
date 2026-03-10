import { useState } from 'react'
import { deployAgent, type AgentRunResult, type ValuationResult } from '../../lib/api'
import { Play, AlertCircle } from 'lucide-react'
import DCFResultsView from './DCFResultsView'
import ExtractionAuditPanel from './ExtractionAuditPanel'

interface Props { dealId: string }

export default function AgentsTab({ dealId }: Props) {
    const [deploying, setDeploying] = useState(false)
    const [result, setResult] = useState<AgentRunResult | null>(null)
    const [valuation, setValuation] = useState<ValuationResult | null>(null)
    const [error, setError] = useState('')

    const [projectionYears, setProjectionYears] = useState(5)
    const [terminalGrowth, setTerminalGrowth] = useState(0.025)
    const [waccOverride, setWaccOverride] = useState('')

    const handleDeploy = async () => {
        setDeploying(true)
        setError('')
        setResult(null)
        setValuation(null)
        try {
            const params: Record<string, unknown> = {
                projection_years: projectionYears,
                terminal_growth_rate: terminalGrowth,
            }
            if (waccOverride) params.wacc_override = parseFloat(waccOverride)

            const res = await deployAgent(dealId, {
                agent_type: 'modeling',
                task_name: 'dcf_model',
                parameters: params,
            })
            setResult(res)
            if (res.valuation_result) setValuation(res.valuation_result)
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : 'Deployment failed'
            setError(msg)
        } finally {
            setDeploying(false)
        }
    }

    return (
        <div className="animate-fade-in">
            {/* Agent Header */}
            <div style={{
                padding: '14px 18px', marginBottom: 16,
                background: '#0a0a0a', border: '1px solid #222', borderRadius: 3,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between'
            }}>
                <div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: '#fff', marginBottom: 2 }}>
                        Financial Modeling Agent
                    </div>
                    <div style={{ fontSize: 11, color: '#555' }}>
                        Maker-Checker Pipeline · Preparer → Auditor → Triangulator → DCF Engine
                    </div>
                </div>
                <span className="badge badge-indigo">DCF</span>
            </div>

            {/* Parameters */}
            <div style={{
                marginBottom: 16, border: '1px solid #222', borderRadius: 3, overflow: 'hidden'
            }}>
                <div style={{ padding: '8px 18px', background: '#0a0a0a', borderBottom: '1px solid #222' }}>
                    <span style={{ fontSize: 10, color: '#555', fontWeight: 700, letterSpacing: '0.1em' }}>PARAMETERS</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 0 }}>
                    {[
                        { label: 'PROJECTION YEARS', value: projectionYears, type: 'number', placeholder: '5', onChange: (v: string) => setProjectionYears(parseInt(v) || 5) },
                        { label: 'TERMINAL GROWTH', value: terminalGrowth, type: 'number', placeholder: '0.025', onChange: (v: string) => setTerminalGrowth(parseFloat(v) || 0.025) },
                        { label: 'WACC OVERRIDE', value: waccOverride, type: 'text', placeholder: '—', onChange: (v: string) => setWaccOverride(v) },
                    ].map((param, i) => (
                        <div key={i} style={{
                            padding: '12px 18px',
                            borderRight: i < 2 ? '1px solid #1a1a1a' : 'none'
                        }}>
                            <div style={{ fontSize: 9, color: '#555', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>
                                {param.label}
                            </div>
                            <input
                                type={param.type}
                                className="input-field"
                                value={param.value}
                                placeholder={param.placeholder}
                                onChange={e => param.onChange(e.target.value)}
                                step={param.type === 'number' ? 0.005 : undefined}
                                style={{ padding: '8px 10px' }}
                            />
                        </div>
                    ))}
                </div>
            </div>

            {/* Deploy */}
            <button
                className="btn-primary"
                onClick={handleDeploy}
                disabled={deploying}
                style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    justifyContent: 'center', width: '100%', padding: '12px 0',
                    marginBottom: 20, fontSize: 13, fontWeight: 700, letterSpacing: '0.04em'
                }}
            >
                {deploying ? (
                    <><div className="spinner" style={{ width: 14, height: 14, borderTopColor: '#000' }} /> PROCESSING...</>
                ) : (
                    <><Play size={14} /> DEPLOY AGENT</>
                )}
            </button>

            {/* Error */}
            {error && (
                <div style={{
                    display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px',
                    background: 'rgba(204,51,51,0.08)', border: '1px solid rgba(204,51,51,0.2)',
                    borderRadius: 3, marginBottom: 16, color: '#cc3333', fontSize: 12
                }}>
                    <AlertCircle size={14} /> {error}
                </div>
            )}

            {/* Completed */}
            {result?.status === 'completed' && (
                <div style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '10px 14px', marginBottom: 16,
                    background: 'rgba(0,204,102,0.06)', border: '1px solid rgba(0,204,102,0.15)',
                    borderRadius: 3
                }}>
                    <span className="status-dot active" />
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#00cc66' }}>PIPELINE COMPLETE</span>
                    <span style={{ fontSize: 11, color: '#444', marginLeft: 'auto', fontFamily: "'SF Mono', Consolas, monospace" }}>
                        {result.run_id?.slice(0, 8)}
                    </span>
                </div>
            )}

            {/* Agent run without valuation */}
            {result && !valuation && (
                <div style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '10px 14px', marginBottom: 16,
                    background: '#0a0a0a', border: '1px solid #222', borderRadius: 3
                }}>
                    <span className={`status-dot ${result.status === 'completed' ? 'active' : 'pending'}`} />
                    <span style={{ fontSize: 12, color: '#aaa' }}>Status: {result.status}</span>
                    <span style={{ fontSize: 11, color: '#444', marginLeft: 'auto', fontFamily: "'SF Mono', Consolas, monospace" }}>
                        {result.run_id?.slice(0, 8)}
                    </span>
                </div>
            )}

            {/* Audit Panel */}
            {valuation?.extraction_quality && (
                <ExtractionAuditPanel data={valuation.extraction_quality} />
            )}

            {/* DCF Results */}
            {valuation && <DCFResultsView data={valuation} />}
        </div>
    )
}
