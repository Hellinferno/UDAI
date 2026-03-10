import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: { 'Content-Type': 'application/json' },
});

// ─── Types ───

export interface Deal {
    id: string;
    name: string;
    company_name: string;
    deal_type: string;
    industry: string;
    deal_stage: string;
    notes?: string;
    created_at: string;
    document_count?: number;
    output_count?: number;
}

export interface DealCreatePayload {
    name: string;
    company_name: string;
    deal_type: string;
    industry: string;
    deal_stage?: string;
    notes?: string;
}

export interface DocumentInfo {
    id: string;
    filename: string;
    file_type: string;
    file_size_bytes: number;
    doc_category?: string;
    parse_status: string;
    uploaded_at: string;
}

export interface UploadFailure {
    filename: string;
    reason: string;
}

export interface AgentRunPayload {
    agent_type: string;
    task_name: string;
    parameters: Record<string, unknown>;
}

export interface AgentRunResult {
    run_id: string;
    status: string;
    steps: Array<Record<string, unknown>>;
    valuation_result?: ValuationResult;
}

export interface ValuationResult {
    header: {
        enterprise_value: number;
        equity_value: number;
        implied_share_price?: number | null;
        wacc: number;
        terminal_method: string;
        currency?: string;
        valuation_basis?: 'share_price' | 'equity_value';
        is_private_company?: boolean;
        company_type?: string;
        liquidity_discount?: number | null;
        control_premium?: number | null;
        projection_horizon_years?: number;
        per_share_value_available?: boolean;
    };
    scenarios?: {
        bear: ScenarioCase;
        base: ScenarioCase;
        bull: ScenarioCase;
    };
    ev_bridge?: Record<string, number | boolean | string | null>;
    tv_crosscheck?: Record<string, unknown>;
    sensitivity_wacc_tgr?: Array<Array<number | null>>;
    sensitivity_labels?: { wacc: number[]; tgr: number[]; metric?: string };
    sbc_adjusted?: Record<string, unknown>;
    operating_leverage?: Record<string, unknown>;
    margin_sensitivity?: Record<string, unknown>;
    capex_sensitivity?: Record<string, unknown>;
    extraction_metadata?: Record<string, unknown>;
    extraction_quality?: {
        mode: string;
        pipeline_stages?: string[];
        audit_trail?: Array<{
            field: string;
            confidence: number;
            source: string;
            auditor_status: string;
            triangulation: string;
        }>;
        triangulation?: {
            overall_verdict: string;
            total_checks: number;
            passed: number;
            failed: number;
            critical_failures: number;
            results: Array<{
                identity: string;
                passed: boolean;
                expected: number;
                actual: number;
                deviation_pct: number;
                details: string;
                severity: string;
            }>;
        };
        company_classification?: {
            is_private_company: boolean;
            entity_type: string;
            listing_status: string;
            cin?: string | null;
            evidence?: string[];
        };
        data_sources?: string[];
        key_field_status?: {
            shares_verified: boolean;
            per_share_value_available: boolean;
            tax_loss_carryforward_modeled: boolean;
        };
    };
    company_classification?: {
        is_private_company: boolean;
        entity_type: string;
        listing_status: string;
        cin?: string | null;
        evidence?: string[];
    };
    warnings?: string[];
}

export interface ScenarioCase {
    label: string;
    revenue_cagr: number;
    ebitda_margin: number;
    valuation: {
        enterprise_value: number;
        equity_value: number;
        share_price?: number | null;
    };
}

export interface OutputInfo {
    id: string;
    agent_run_id: string;
    filename: string;
    output_type: string;
    output_category: string;
    review_status: string;
    created_at: string;
}

interface APIResponse<T> {
    success: boolean;
    data: T;
    meta: { timestamp: string; request_id: string };
}

// ─── Deals ───

export async function fetchDeals(): Promise<Deal[]> {
    const res = await api.get<APIResponse<{ deals: Deal[]; total: number }>>('/deals');
    return res.data.data.deals;
}

export async function fetchDeal(dealId: string): Promise<Deal> {
    const res = await api.get<APIResponse<Deal>>(`/deals/${dealId}`);
    return res.data.data;
}

export async function createDeal(payload: DealCreatePayload): Promise<Deal> {
    const res = await api.post<APIResponse<Deal>>('/deals', payload);
    return res.data.data;
}

export async function updateDeal(dealId: string, payload: Partial<DealCreatePayload>): Promise<void> {
    await api.patch(`/deals/${dealId}`, payload);
}

export async function deleteDeal(dealId: string): Promise<void> {
    await api.delete(`/deals/${dealId}`);
}

// ─── Documents ───

export async function fetchDocuments(dealId: string): Promise<DocumentInfo[]> {
    const res = await api.get<APIResponse<DocumentInfo[]>>(`/deals/${dealId}/documents`);
    return res.data.data;
}

export async function uploadDocuments(
    dealId: string,
    files: File[],
    category?: string
): Promise<{ uploaded: DocumentInfo[]; failed: UploadFailure[] }> {
    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));
    if (category) formData.append('category', category);

    const res = await api.post<APIResponse<{ uploaded: DocumentInfo[]; failed: UploadFailure[] }>>(
        `/deals/${dealId}/documents`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    const payload = res.data.data as { uploaded: DocumentInfo[]; failed?: UploadFailure[] };
    return {
        uploaded: payload.uploaded ?? [],
        failed: payload.failed ?? [],
    };
}

export async function deleteDocument(dealId: string, docId: string): Promise<void> {
    await api.delete(`/deals/${dealId}/documents/${docId}`);
}

// ─── Agents ───

export async function deployAgent(dealId: string, payload: AgentRunPayload): Promise<AgentRunResult> {
    const res = await api.post<APIResponse<AgentRunResult>>(`/deals/${dealId}/agents/run`, payload);
    return res.data.data;
}

// ─── Outputs ───

export async function fetchOutputs(dealId: string): Promise<OutputInfo[]> {
    const res = await api.get<APIResponse<OutputInfo[]>>(`/deals/${dealId}/outputs`);
    return res.data.data;
}

export function getDownloadUrl(outputId: string): string {
    return `${API_BASE_URL}/outputs/${outputId}/download`;
}
