import { useCallback, useEffect, useState } from 'react'
import axios from 'axios'
import {
    deployAgent,
    fetchAgentRun,
    fetchDocuments,
    type AgentRunResult,
    type ValuationResult,
} from '../../lib/api'
import { Play, AlertCircle } from 'lucide-react'
import DCFResultsView from './DCFResultsView'
import ExtractionAuditPanel from './ExtractionAuditPanel'

interface Props { dealId: string }

export default function AgentsTab({ dealId }: Props) {
    const [deploying, setDeploying] = useState(false)
    const [result, setResult] = useState<AgentRunResult | null>(null)
    const [valuation, setValuation] = useState<ValuationResult | null>(null)
    const [error, setError] = useState('')
    const [activeRunId, setActiveRunId] = useState<string | null>(null)
    const [documentsReady, setDocumentsReady] = useState(true)
    const [documentStatusNote, setDocumentStatusNote] = useState('')

    const [projectionYears, setProjectionYears] = useState(5)
    const [terminalGrowth, setTerminalGrowth] = useState(0.025)
    const [waccOverride, setWaccOverride] = useState('')
    const [currentMarketCap, setCurrentMarketCap] = useState('')
    const [currentSharePrice, setCurrentSharePrice] = useState('')

    const refreshDocumentReadiness = useCallback(async () => {
        try {
            const docs = await fetchDocuments(dealId)
            const blocked = docs.filter(doc => doc.parse_status !== 'parsed')
            if (blocked.length === 0) {
                setDocumentsReady(true)
                setDocumentStatusNote(docs.length > 0 ? 'All uploaded documents are parsed and ready.' : '')
            } else {
                setDocumentsReady(false)
                setDocumentStatusNote(
                    `Waiting on ${blocked.length} document(s): ${blocked.map(doc => doc.filename).slice(0, 3).join(', ')}`
                )
            }
            return blocked.length === 0
        } catch {
            setDocumentsReady(true)
            setDocumentStatusNote('')
            return true
        }
    }, [dealId])

    useEffect(() => {
        refreshDocumentReadiness()
    }, [refreshDocumentReadiness])

    useEffect(() => {
        if (documentsReady) return
        const interval = window.setInterval(() => {
            refreshDocumentReadiness()
        }, 3000)
        return () => window.clearInterval(interval)
    }, [documentsReady, refreshDocumentReadiness])

    useEffect(() => {
        if (!activeRunId) return

        const interval = window.setInterval(async () => {
            try {
                const run = await fetchAgentRun(dealId, activeRunId)
                setResult(run)
                if (run.valuation_result) setValuation(run.valuation_result)

                if (run.status === 'completed') {
                    setDeploying(false)
                    setActiveRunId(null)
                } else if (run.status === 'failed') {
                    setDeploying(false)
                    setActiveRunId(null)
                    setError(run.error_message || 'Agent run failed')
                }
            } catch {
                setDeploying(false)
                setActiveRunId(null)
                setError('Failed to refresh agent status')
            }
        }, 2500)

        return () => window.clearInterval(interval)
    }, [activeRunId, dealId])

    const handleDeploy = async () => {
        setDeploying(true)
        setError('')
        setResult(null)
        setValuation(null)

        const docsReady = await refreshDocumentReadiness()
        if (!docsReady) {
            setDeploying(false)
            setError('Documents are still parsing. Wait until all files are marked parsed before running the agent.')
            return
        }

        try {
            const params: Record<string, unknown> = {
                projection_years: projectionYears,
                terminal_growth_rate: terminalGrowth,
            }
            if (waccOverride) params.wacc_override = parseFloat(waccOverride)
            if (currentMarketCap) params.current_market_cap = parseFloat(currentMarketCap)
            if (currentSharePrice) params.current_share_price = parseFloat(currentSharePrice)

            const res = await deployAgent(dealId, {
                agent_type: 'modeling',
                task_name: 'dcf_model',
                parameters: params,
            })
            setResult(res)
            if (res.valuation_result) setValuation(res.valuation_result)

            if (res.status === 'completed') {
                setDeploying(false)
            } else if (res.status === 'failed') {
                setDeploying(false)
                setError(res.error_message || 'Agent run failed')
            } else {
                setActiveRunId(res.run_id)
            }
        } catch (err: unknown) {
            let msg = err instanceof Error ? err.message : 'Deployment failed'
            if (axios.isAxiosError(err) && err.code === 'ECONNABORTED') {
                msg = 'Agent run is taking longer than the browser timeout. Please wait and try again.'
            }
            if (axios.isAxiosError(err)) {
                msg = (err.response?.data as { detail?: string } | undefined)?.detail || msg
            }
            setError(msg)
            setDeploying(false)
            setActiveRunId(null)
        }
    }

    return (
        <div className="animate-fade-in">
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

            {!documentsReady && documentStatusNote && (
                <div style={{
                    display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px',
                    background: 'rgba(255,153,0,0.08)', border: '1px solid rgba(255,153,0,0.2)',
                    borderRadius: 3, marginBottom: 16, color: '#ff9900', fontSize: 12
                }}>
                    <AlertCircle size={14} /> {documentStatusNote}
                </div>
            )}

            <div style={{
                marginBottom: 16, border: '1px solid #222', borderRadius: 3, overflow: 'hidden'
            }}>
                <div style={{ padding: '8px 18px', background: '#0a0a0a', borderBottom: '1px solid #222' }}>
                    <span style={{ fontSize: 10, color: '#555', fontWeight: 700, letterSpacing: '0.1em' }}>PARAMETERS</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 0 }}>
                    {[
                        { label: 'PROJECTION YEARS', value: projectionYears, type: 'number', placeholder: '5', onChange: (v: string) => setProjectionYears(parseInt(v, 10) || 5) },
                        { label: 'TERMINAL GROWTH', value: terminalGrowth, type: 'number', placeholder: '0.025', onChange: (v: string) => setTerminalGrowth(parseFloat(v) || 0.025) },
                        { label: 'WACC OVERRIDE', value: waccOverride, type: 'text', placeholder: '—', onChange: (v: string) => setWaccOverride(v) },
                        { label: 'CURRENT MARKET CAP', value: currentMarketCap, type: 'text', placeholder: 'Optional', onChange: (v: string) => setCurrentMarketCap(v) },
                        { label: 'CURRENT SHARE PRICE', value: currentSharePrice, type: 'text', placeholder: 'Optional', onChange: (v: string) => setCurrentSharePrice(v) },
                    ].map((param, i) => (
                        <div key={i} style={{
                            padding: '12px 18px',
                            borderRight: '1px solid #1a1a1a',
                            borderBottom: i < 3 ? '1px solid #1a1a1a' : 'none'
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

            <button
                className="btn-primary"
                onClick={handleDeploy}
                disabled={deploying || !documentsReady}
                style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    justifyContent: 'center', width: '100%', padding: '12px 0',
                    marginBottom: 20, fontSize: 13, fontWeight: 700, letterSpacing: '0.04em',
                    opacity: deploying || !documentsReady ? 0.7 : 1,
                }}
            >
                {deploying ? (
                    <><div className="spinner" style={{ width: 14, height: 14, borderTopColor: '#000' }} /> PROCESSING...</>
                ) : (
                    <><Play size={14} /> DEPLOY AGENT</>
                )}
            </button>

            {error && (
                <div style={{
                    display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px',
                    background: 'rgba(204,51,51,0.08)', border: '1px solid rgba(204,51,51,0.2)',
                    borderRadius: 3, marginBottom: 16, color: '#cc3333', fontSize: 12
                }}>
                    <AlertCircle size={14} /> {error}
                </div>
            )}

            {result && (
                <div style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '10px 14px', marginBottom: 16,
                    background: result.status === 'completed'
                        ? 'rgba(0,204,102,0.06)'
                        : result.status === 'failed'
                            ? 'rgba(204,51,51,0.08)'
                            : '#0a0a0a',
                    border: result.status === 'completed'
                        ? '1px solid rgba(0,204,102,0.15)'
                        : result.status === 'failed'
                            ? '1px solid rgba(204,51,51,0.2)'
                            : '1px solid #222',
                    borderRadius: 3
                }}>
                    <span className={`status-dot ${result.status === 'completed' ? 'active' : 'pending'}`} />
                    <span style={{ fontSize: 12, fontWeight: 700, color: result.status === 'completed' ? '#00cc66' : '#aaa' }}>
                        STATUS: {result.status.toUpperCase()}
                    </span>
                    <span style={{ fontSize: 11, color: '#444', marginLeft: 'auto', fontFamily: "'SF Mono', Consolas, monospace" }}>
                        {result.run_id?.slice(0, 8)}
                    </span>
                </div>
            )}

            {valuation?.extraction_quality && (
                <ExtractionAuditPanel data={valuation.extraction_quality} />
            )}

            {valuation && <DCFResultsView data={valuation} />}
        </div>
    )
}
