import { useState, useEffect, useCallback } from 'react'
import { fetchOutputs, getDownloadUrl, type OutputInfo } from '../../lib/api'
import { Download, Clock } from 'lucide-react'

interface Props { dealId: string }

export default function OutputsTab({ dealId }: Props) {
    const [outputs, setOutputs] = useState<OutputInfo[]>([])
    const [loading, setLoading] = useState(true)

    const load = useCallback(async () => {
        try {
            const data = await fetchOutputs(dealId)
            setOutputs(data)
        } catch { setOutputs([]) }
        finally { setLoading(false) }
    }, [dealId])

    useEffect(() => { load() }, [load])

    if (loading) {
        return (
            <div style={{ textAlign: 'center', padding: 60 }}>
                <div className="spinner" style={{ margin: '0 auto' }} />
            </div>
        )
    }

    if (outputs.length === 0) {
        return (
            <div className="animate-fade-in" style={{ textAlign: 'center', padding: 60, color: '#444', fontSize: 12 }}>
                No outputs generated yet — deploy an agent first
            </div>
        )
    }

    return (
        <div className="animate-fade-in">
            <div style={{ border: '1px solid #222', borderRadius: 3, overflow: 'hidden' }}>
                {outputs.map((out, i) => (
                    <div key={out.id} style={{
                        display: 'flex', alignItems: 'center', padding: '14px 18px',
                        borderBottom: i < outputs.length - 1 ? '1px solid #151515' : 'none',
                    }}>
                        <div style={{ flex: 1 }}>
                            <div style={{ fontSize: 13, fontWeight: 600, color: '#fff', marginBottom: 2 }}>{out.filename}</div>
                            <div style={{ fontSize: 11, color: '#555', display: 'flex', alignItems: 'center', gap: 6 }}>
                                <Clock size={10} />
                                {new Date(out.created_at).toLocaleString()} · {out.output_type}
                            </div>
                        </div>
                        <span className={`badge ${out.review_status === 'approved' ? 'badge-emerald' : 'badge-amber'}`} style={{ marginRight: 12 }}>
                            {out.review_status}
                        </span>
                        <a
                            href={getDownloadUrl(out.id)}
                            className="btn-primary"
                            style={{ padding: '6px 14px', fontSize: 11, textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 5 }}
                            download
                        >
                            <Download size={11} /> DOWNLOAD
                        </a>
                    </div>
                ))}
            </div>
        </div>
    )
}
