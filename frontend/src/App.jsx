import { useState, useRef, useEffect } from 'react'
import './index.css' // Import basic reset, tailwind is in index.html via CDN

const API_BASE = 'http://localhost:8000'

const SUGGESTED_QUESTIONS = [
  "What is the total revenue?",
  "Which segment has the highest churn?",
  "What are the biggest churn drivers?",
  "Show the top 10 customers by predicted CLV",
  "Which customers should we prioritize for retention?",
  "What is the average transaction value?"
]

const CAMPAIGN_QUESTIONS = [
  "Who should we target for retention?",
  "Which segment has the highest campaign propensity?",
  "Show high CLV high risk customers",
  "Did treatment perform better than control?",
  "Which campaign had the highest conversion?",
  "What was the conversion lift?"
]

function App() {
  const [question, setQuestion] = useState('')
  const [conversations, setConversations] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [conversations])

  const handleSubmit = async (e) => {
    e?.preventDefault()
    const q = question.trim()
    if (!q || loading) return

    setConversations(prev => [...prev, { type: 'question', text: q }])
    setQuestion('')
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE}/api/ai/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      })

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`)
      }

      const data = await response.json()
      setConversations(prev => [...prev, { type: 'answer', data }])
    } catch (err) {
      setError(err.message)
      setConversations(prev => [...prev, {
        type: 'answer',
        data: {
          success: false,
          summary: `Unable to complete analysis. We couldn't retrieve the requested data.`,
          error: err.message,
        }
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleSuggestion = (q) => {
    setQuestion(q)
    // Focus input and set value, but user needs to hit enter or click send. Or we auto-submit.
    // Let's auto-submit for better UX.
    setTimeout(() => {
        const form = document.getElementById('query-form')
        if (form) form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }))
    }, 10)
  }

  return (
    <div className="flex h-screen w-screen bg-background">
      {/* SideNavBar */}
      <nav className="bg-surface dark:bg-surface text-secondary dark:text-secondary font-body-md text-body-md h-screen w-64 fixed left-0 top-0 border-r border-outline-variant dark:border-outline-variant flex flex-col py-container-padding z-50">
        <div className="px-container-padding mb-density-spacious flex items-center gap-density-comfortable">
          <div className="w-8 h-8 rounded-full bg-secondary-container text-on-secondary-container flex items-center justify-center font-label-caps text-label-caps overflow-hidden">
            <span className="material-symbols-outlined text-[16px]">person</span>
          </div>
          <div>
            <div className="font-headline-sm text-headline-sm font-bold text-on-surface dark:text-on-surface">FinSight 360</div>
            <div className="font-body-sm text-body-sm text-on-surface-variant">Intelligence Admin</div>
          </div>
        </div>
        <ul className="flex flex-col gap-unit px-unit">
          <li>
            <a className="flex items-center gap-density-comfortable px-density-comfortable py-density-comfortable rounded text-secondary font-bold border-r-2 border-secondary bg-surface-container-high transition-colors hover:bg-surface-container-low" href="#">
              <span className="material-symbols-outlined" data-weight="fill">dashboard</span>
              <span>Overview</span>
            </a>
          </li>
          <li>
            <a className="flex items-center gap-density-comfortable px-density-comfortable py-density-comfortable rounded text-on-surface-variant font-medium hover:bg-surface-container-low transition-colors" href="#">
              <span className="material-symbols-outlined">group</span>
              <span>Customers</span>
            </a>
          </li>
          <li>
            <a className="flex items-center gap-density-comfortable px-density-comfortable py-density-comfortable rounded text-on-surface-variant font-medium hover:bg-surface-container-low transition-colors" href="#">
              <span className="material-symbols-outlined">warning</span>
              <span>Churn & Risk</span>
            </a>
          </li>
          <li>
            <a className="flex items-center gap-density-comfortable px-density-comfortable py-density-comfortable rounded text-on-surface-variant font-medium hover:bg-surface-container-low transition-colors" href="#">
              <span className="material-symbols-outlined">trending_up</span>
              <span>CLV</span>
            </a>
          </li>
          <li>
            <a className="flex items-center gap-density-comfortable px-density-comfortable py-density-comfortable rounded text-on-surface-variant font-medium hover:bg-surface-container-low transition-colors" href="#">
              <span className="material-symbols-outlined">pie_chart</span>
              <span>Segments</span>
            </a>
          </li>
        </ul>
      </nav>

      {/* Main Content Wrapper */}
      <div className="flex-1 ml-64 flex flex-col h-screen overflow-hidden relative">
        {/* TopNavBar */}
        <header className="bg-surface dark:bg-surface text-secondary dark:text-secondary font-headline-sm text-headline-sm w-full top-0 sticky z-40 border-b border-outline-variant flex justify-between items-center h-16 px-container-padding flex-shrink-0">
          <div className="font-headline-sm text-headline-sm font-bold text-on-surface">FinSight 360 | Customer Intelligence & Campaigns</div>
          <div className="flex items-center gap-density-spacious">
            <div className="flex items-center gap-density-compact text-secondary font-body-sm text-body-sm font-medium">
              <span className="w-2 h-2 rounded-full bg-secondary"></span>
              Connected
            </div>
            <div className="flex gap-density-comfortable">
              <button className="text-on-surface-variant hover:text-primary transition-colors flex items-center justify-center p-unit rounded hover:bg-surface-container">
                <span className="material-symbols-outlined">notifications</span>
              </button>
              <button className="text-on-surface-variant hover:text-primary transition-colors flex items-center justify-center p-unit rounded hover:bg-surface-container">
                <span className="material-symbols-outlined">help</span>
              </button>
              <button className="text-on-surface-variant hover:text-primary transition-colors flex items-center justify-center p-unit rounded hover:bg-surface-container">
                <span className="material-symbols-outlined">settings</span>
              </button>
            </div>
          </div>
        </header>

        {/* Canvas / Dashboard Area */}
        <main className="flex-1 overflow-y-auto bg-background p-container-padding pb-[120px] table-scroll">
          <div className="max-w-7xl mx-auto flex flex-col gap-12">
            
            {conversations.length === 0 && (
              <section className="w-full max-w-5xl rounded-lg border border-outline-variant bg-surface-container p-container-padding">
                <div className="flex items-start gap-density-comfortable mb-density-spacious">
                  <span className="material-symbols-outlined text-secondary">ads_click</span>
                  <div>
                    <h2 className="font-headline-md text-headline-md text-on-surface">Campaign Targeting & Experimentation</h2>
                    <p className="font-body-md text-body-md text-on-surface-variant max-w-3xl">Use the assistant to find targetable customers, inspect propensity and priority, and review Control vs Treatment performance from the warehouse.</p>
                  </div>
                </div>
                <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
                  {CAMPAIGN_QUESTIONS.map((q, i) => (
                    <button
                      key={i}
                      onClick={() => handleSuggestion(q)}
                      className="rounded-lg border border-outline-variant bg-surface-container-high px-4 py-3 text-left hover:bg-surface-container-highest transition-colors"
                    >
                      <div className="font-label-caps text-label-caps text-secondary uppercase tracking-wider mb-1">Campaign</div>
                      <div className="font-body-md text-body-md text-on-surface leading-snug">{q}</div>
                    </button>
                  ))}
                </div>
              </section>
            )}

            {conversations.length === 0 && (
              <div className="mt-20 flex flex-col items-center justify-center text-center">
                <span className="material-symbols-outlined text-6xl text-surface-tint mb-4 opacity-50">data_exploration</span>
                <h2 className="font-display-lg text-display-lg text-on-surface mb-2">What would you like to know?</h2>
                <p className="text-on-surface-variant max-w-lg mb-8 font-body-md text-body-md">Explore customers, churn, CLV, revenue and segments using natural language.</p>
                <div className="flex flex-wrap justify-center gap-4 max-w-2xl">
                  {SUGGESTED_QUESTIONS.map((q, i) => (
                    <button
                      key={i}
                      onClick={() => handleSuggestion(q)}
                      className="bg-surface-container-highest hover:bg-surface-variant text-on-surface border border-outline-variant px-4 py-2 rounded-full font-body-md text-body-md transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {conversations.map((msg, i) => (
              <div key={i} className="flex flex-col gap-4">
                {msg.type === 'question' ? (
                  <div className="bg-surface-container-high rounded-lg border border-outline-variant p-density-comfortable inline-block self-end max-w-3xl mr-0 ml-auto">
                    <span className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider mb-1 block">You Asked</span>
                    <p className="font-body-md text-body-md text-on-surface">{msg.text}</p>
                  </div>
                ) : (
                  <AnswerCard data={msg.data} />
                )}
              </div>
            ))}

            {loading && (
              <div className="flex gap-4">
                <div className="bg-surface-container rounded-lg border border-outline-variant p-container-padding flex items-center gap-4 animate-pulse w-full max-w-3xl">
                  <span className="material-symbols-outlined text-secondary animate-spin">hourglass_empty</span>
                  <p className="text-on-surface-variant font-body-md text-body-md">Analyzing your question... querying analytics warehouse.</p>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </main>

        {/* Query Console (Footer Nav) */}
        <div className="bg-surface-container text-secondary font-body-md text-body-md text-on-surface-variant fixed bottom-0 right-0 w-[calc(100%-16rem)] border-t border-outline-variant flex flex-col z-40">
          
          {/* Execution Metrics (Only show for the last successful answer) */}
          {conversations.length > 0 && conversations[conversations.length - 1].type === 'answer' && conversations[conversations.length - 1].data?.success && (
            <div className="px-container-padding py-density-compact border-b border-outline-variant bg-surface-container-lowest flex justify-between items-center font-tabular-data text-tabular-data text-on-surface-variant text-[11px]">
              <div className="flex items-center gap-density-comfortable">
                <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-[#10b981]"></span> Query completed</span>
                {conversations[conversations.length - 1].data?.processing_time_ms && (
                  <>
                    <span>·</span>
                    <span>{conversations[conversations.length - 1].data.processing_time_ms} ms execution</span>
                  </>
                )}
                {conversations[conversations.length - 1].data?.data?.row_count !== undefined && (
                  <>
                    <span>·</span>
                    <span>{conversations[conversations.length - 1].data.data.row_count} rows returned</span>
                  </>
                )}
              </div>
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[14px]">database</span> Data Warehouse
              </div>
            </div>
          )}

          <div className="flex items-center gap-gutter p-container-padding bg-surface-container">
            <form id="query-form" onSubmit={handleSubmit} className="flex-1 flex gap-gutter w-full">
              <div className="flex-1 relative">
                <span className="material-symbols-outlined absolute left-density-comfortable top-1/2 transform -translate-y-1/2 text-on-surface-variant">search</span>
                <input 
                  ref={inputRef}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  disabled={loading}
                  className="w-full bg-surface-dim border border-outline-variant rounded-lg py-density-comfortable pl-10 pr-4 text-on-surface font-body-md text-body-md focus:border-secondary focus:ring-1 focus:ring-secondary transition-all outline-none placeholder-on-surface-variant disabled:opacity-50" 
                  placeholder="Ask about customers, churn, CLV, revenue or segments..." 
                  type="text"
                />
              </div>
              <button 
                type="submit"
                disabled={loading || !question.trim()}
                className="bg-secondary text-on-secondary hover:bg-secondary-container disabled:opacity-50 disabled:hover:bg-secondary transition-colors px-container-padding py-density-comfortable rounded-lg font-body-md text-body-md font-medium flex items-center gap-2 border border-transparent"
              >
                {loading ? 'Thinking...' : 'Send'} <span className="material-symbols-outlined text-[18px]">send</span>
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}


function AnswerCard({ data }) {
  const [showSQL, setShowSQL] = useState(false)

  if (!data) return null
  const isError = !data.success && data.error

  if (isError) {
    return (
      <div className="bg-[#93000a] bg-opacity-20 rounded-lg border border-[#ffb4ab] p-container-padding w-full max-w-3xl">
        <div className="flex items-start gap-density-comfortable">
          <div className="mt-unit text-[#ffb4ab]">
            <span className="material-symbols-outlined">error</span>
          </div>
          <div>
            <h2 className="font-headline-sm text-headline-sm text-[#ffdad6] mb-density-compact">Unable to complete analysis</h2>
            <p className="font-body-md text-body-md text-[#ffb4ab]">{data.summary}</p>
            {data.error && (
              <details className="mt-4 text-[#ffb4ab] text-sm opacity-80 cursor-pointer">
                <summary>Technical details</summary>
                <pre className="mt-2 p-2 bg-[#690005] rounded text-xs overflow-auto">{data.error}</pre>
              </details>
            )}
          </div>
        </div>
      </div>
    )
  }

  const hasTable = data.data && data.data.rows && data.data.rows.length > 0;
  const hasShap = data.shap_drivers && data.shap_drivers.length > 0;
  const hasRecs = data.data_recommendations && data.data_recommendations.length > 0;
  const hasInsights = data.insights && data.insights.length > 0;

  return (
    <div className="grid grid-cols-12 gap-gutter w-full">
      {/* Summary */}
      <div className="col-span-12 bg-surface-container rounded-lg border border-outline-variant p-container-padding">
        <div className="flex items-start gap-density-comfortable">
          <div className="mt-unit text-secondary">
            <span className="material-symbols-outlined">insights</span>
          </div>
          <div className="w-full">
            <div className="flex justify-between items-center mb-2">
               <h2 className="font-headline-md text-headline-md text-on-surface">{data.intent ? data.intent.replace(/_/g, ' ') : 'Analysis'}</h2>
            </div>
            <p className="font-body-md text-body-md text-on-surface-variant max-w-4xl whitespace-pre-wrap">{data.summary}</p>
            
            {hasInsights && (
              <ul className="mt-4 space-y-1 list-disc pl-5 text-on-surface-variant font-body-md">
                {data.insights.map((ins, i) => (
                  <li key={i}>{ins}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {/* SHAP Risk Drivers */}
      {hasShap && (
        <div className="col-span-12 bg-surface-container rounded-lg border border-outline-variant p-container-padding">
          <div className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider mb-density-spacious flex items-center gap-2">
            <span className="material-symbols-outlined text-[16px]">science</span>
            Model Explanation (SHAP Risk Drivers)
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
            {data.shap_drivers.map((d, i) => {
               // Assign color/width based on rank for visualization
               const isHigh = i === 0;
               const isMed = i === 1;
               const colorClass = isHigh ? 'bg-error' : (isMed ? 'bg-[#f59e0b]' : 'bg-[#10b981]');
               const textClass = isHigh ? 'text-error' : (isMed ? 'text-[#f59e0b]' : 'text-[#10b981]');
               const width = isHigh ? '75%' : (isMed ? '45%' : '20%');
               const impactText = isHigh ? 'High Impact' : (isMed ? 'Medium Impact' : 'Low Impact');

               return (
                <div key={i}>
                  <div className="flex justify-between font-body-sm text-body-sm mb-density-compact">
                    <span className="text-on-surface">{d.display_name}</span>
                    <span className={`${textClass} font-tabular-data`}>{impactText}</span>
                  </div>
                  <div className="h-2 bg-surface-container-highest rounded-full overflow-hidden border border-outline-variant">
                    <div className={`h-full ${colorClass}`} style={{ width }}></div>
                  </div>
                  <p className="text-[10px] text-on-surface-variant mt-1 ml-1">{d.recommendation}</p>
                </div>
               )
            })}
          </div>
        </div>
      )}

      {/* Data Table */}
      {hasTable && (
        <div className="col-span-12 bg-surface-container rounded-lg border border-outline-variant overflow-hidden">
          <div className="p-density-comfortable border-b border-outline-variant flex justify-between items-center bg-surface-container-low">
            <div className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px]">table_chart</span>
              Dataset
            </div>
            <div className="text-[11px] text-on-surface-variant font-tabular-data">
              {data.data.row_count} rows {data.data.truncated && "(Truncated)"}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-outline-variant bg-surface-container-lowest whitespace-nowrap">
                  {data.data.columns.filter(c => !c.endsWith('_display')).map((col, i) => (
                    <th key={i} className="p-density-comfortable font-label-caps text-label-caps text-on-surface-variant font-medium">
                      {col.replace(/_/g, ' ')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="font-tabular-data text-tabular-data text-on-surface divide-y divide-outline-variant">
                {data.data.rows.map((row, i) => (
                  <tr key={i} className="hover:bg-surface-container-highest transition-colors group cursor-default">
                    {data.data.columns.filter(c => !c.endsWith('_display')).map((col, j) => (
                      <td key={j} className="p-density-comfortable whitespace-nowrap">
                        {formatValue(row[col])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recommended Actions */}
      {hasRecs && (
        <div className="col-span-12 md:col-span-6 bg-surface-container rounded-lg border border-outline-variant p-container-padding">
          <div className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider mb-density-comfortable flex items-center gap-2">
            <span className="material-symbols-outlined text-[16px]">lightbulb</span> 
            Recommended Actions
          </div>
          <ul className="space-y-3 text-on-surface-variant font-body-md text-body-md">
            {data.data_recommendations.map((rec, i) => (
              <li key={i} className="flex flex-col gap-1 border-l-2 pl-3 border-secondary bg-surface-container-low p-2 rounded-r">
                <span className="font-medium text-on-surface">{rec.text}</span>
                {rec.grounding && <span className="text-[11px] font-tabular-data text-secondary opacity-80">{rec.grounding}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* SQL View */}
      {data.sql && (
        <div className={`col-span-12 ${hasRecs ? 'md:col-span-6' : ''} bg-surface-container rounded-lg border border-outline-variant flex flex-col overflow-hidden h-fit`}>
          <div 
            className="p-density-comfortable border-b border-outline-variant flex justify-between items-center bg-surface-container-low cursor-pointer hover:bg-surface-container transition-colors" 
            onClick={() => setShowSQL(!showSQL)}
          >
            <div className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider flex items-center gap-2">
              <span className={`material-symbols-outlined text-[16px] transform transition-transform ${showSQL ? 'rotate-0' : '-rotate-90'}`}>expand_more</span>
              View generated SQL
            </div>
            <span className="bg-surface-variant text-on-surface-variant px-2 py-1 rounded text-[10px] font-label-caps border border-outline-variant uppercase tracking-wider">Read-only</span>
          </div>
          {showSQL && (
            <div className="p-container-padding bg-[#020617] flex-1 relative font-code-block text-code-block text-on-surface overflow-x-auto">
              <pre className="m-0 text-[#98c379] text-[12px]">{data.sql}</pre>
            </div>
          )}
        </div>
      )}

    </div>
  )
}


function formatValue(val) {
  if (val === null || val === undefined) return '—'
  if (typeof val === 'number') {
    if (val > 10000) return `₹${val.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
    if (val < 1 && val >= 0.0001) return (val * 100).toFixed(2) + '%'
    return val.toLocaleString('en-IN', { maximumFractionDigits: 2 })
  }
  return String(val)
}

export default App
