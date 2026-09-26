import { useEffect, useMemo, useState } from 'react';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const STARTER_TEXT = 'Эйфелева башня была построена в 1889 году и находится в Лондоне. Её высота составляет 324 метра, а в 2024 году она оставалась самым высоким сооружением в мире.';

const coordinates = (quote) => {
  const start = STARTER_TEXT.indexOf(quote);
  return { original_quote: quote, start_char: start, end_char: start + quote.length };
};

const DEMO_ANALYSIS = {
  analysis_id: 'senim-eiffel-2026',
  processing_time_ms: 4380,
  timestamp: '2026-09-26T02:32:00.000Z',
  summary: { total_claims: 4, supported: 1, contradicted: 2, partially_supported: 1, unverified: 0, not_fact_checkable: 0, conflicting: 0, verification_score: 0.38 },
  claims: [
    {
      id: 1, type: 'temporal', verdict: 'supported', confidence: 0.98, evidence_sufficiency: 'DIRECT',
      text: 'Эйфелева башня была построена в 1889 году.', ...coordinates('Эйфелева башня была построена в 1889 году'),
      explanation: 'Официальный сайт башни указывает, что она была открыта 31 марта 1889 года для Всемирной выставки в Париже.',
      why_verdict: ['Утверждение выделено как самостоятельный исторический факт.', 'Первичный источник прямо называет 1889 год и дату открытия.', 'Найденное доказательство не противоречит ни одной части claim.'],
      sources: [{ title: 'The Eiffel Tower: history and key dates', domain: 'toureiffel.paris', url: 'https://www.toureiffel.paris/en/the-monument/history', snippet: 'The Eiffel Tower was inaugurated on 31 March 1889 for the Universal Exhibition.', quality: 'Primary source', freshness: 'Official reference', stance: 'SUPPORTS' }],
    },
    {
      id: 2, type: 'factual', verdict: 'contradicted', confidence: 0.99, evidence_sufficiency: 'DIRECT',
      text: 'Эйфелева башня находится в Лондоне.', ...coordinates('находится в Лондоне'),
      explanation: 'Надёжные источники единодушно размещают Эйфелеву башню на Марсовом поле в Париже, Франция. Утверждение о Лондоне противоречит доказательствам.',
      why_verdict: ['Claim содержит проверяемое утверждение о геолокации.', 'Официальный источник называет Champ de Mars, Paris, France.', 'Независимый справочный источник подтверждает ту же локацию.', 'Ни один источник не поддерживает вариант с Лондоном.'],
      sources: [
        { title: 'Eiffel Tower — official visitor information', domain: 'toureiffel.paris', url: 'https://www.toureiffel.paris/en', snippet: 'The Eiffel Tower stands on the Champ de Mars in Paris, France.', quality: 'Primary source', freshness: 'Official reference', stance: 'CONTRADICTS' },
        { title: 'Eiffel Tower', domain: 'britannica.com', url: 'https://www.britannica.com/topic/Eiffel-Tower-Paris-France', snippet: 'Landmark of Paris, located on the Champ de Mars on the left bank of the Seine.', quality: 'Reference', freshness: 'Reviewed reference', stance: 'CONTRADICTS' },
      ],
    },
    {
      id: 3, type: 'numerical', verdict: 'partially_supported', confidence: 0.96, evidence_sufficiency: 'DIRECT',
      text: 'Высота Эйфелевой башни составляет 324 метра.', ...coordinates('Её высота составляет 324 метра'),
      explanation: '324 метра — исторически употребляемая цифра, но официальная текущая высота вместе с антеннами составляет 330 метров. Число требует контекста и даты.',
      why_verdict: ['Числовой claim сопоставлен с текущей официальной спецификацией.', 'Источник подтверждает, что у башни была высота 324 м в прежних описаниях.', 'Текущая официальная цифра — 330 м вместе с антеннами.', 'Формулировка без даты и уточнения высоты неполна.'],
      sources: [{ title: 'The Eiffel Tower in figures', domain: 'toureiffel.paris', url: 'https://www.toureiffel.paris/en/the-monument/key-figures', snippet: 'Today, the Eiffel Tower is 330 metres high, including its antennas.', quality: 'Primary source', freshness: 'Official reference', stance: 'CONTRADICTS' }],
    },
    {
      id: 4, type: 'comparative', verdict: 'contradicted', confidence: 0.99, evidence_sufficiency: 'COMBINED',
      text: 'В 2024 году Эйфелева башня оставалась самым высоким сооружением в мире.', ...coordinates('в 2024 году она оставалась самым высоким сооружением в мире'),
      explanation: 'Это утверждение противоречит данным о Burj Khalifa: его высота 828 метров, что существенно больше высоты Эйфелевой башни.',
      why_verdict: ['Сравнительный claim привязан к 2024 году.', 'Проверка требует источника с актуальным мировым рекордом.', 'Официальная страница Burj Khalifa называет высоту 828 м и мировой рекорд с 2010 года.', 'Доказательство прямо исключает Эйфелеву башню из позиции самого высокого сооружения.'],
      sources: [{ title: 'Burj Khalifa facts and figures', domain: 'burjkhalifa.ae', url: 'https://www.burjkhalifa.ae/en/the-tower/facts-figures/', snippet: 'At 828 metres, Burj Khalifa has been the tallest building in the world since 2010.', quality: 'Primary source', freshness: 'Official reference', stance: 'CONTRADICTS' }],
    },
  ],
};

const VERDICTS = {
  supported: { label: 'Подтверждено', markdown: '🟢 SUPPORTED', tone: 'positive', icon: 'check' },
  contradicted: { label: 'Опровергнуто', markdown: '🔴 CONTRADICTED', tone: 'negative', icon: 'close' },
  partially_supported: { label: 'Частично подтверждено', markdown: '🟡 PARTIAL', tone: 'warning', icon: 'half' },
  unverified: { label: 'Недостаточно данных', markdown: '⚪ UNVERIFIED', tone: 'neutral', icon: 'question' },
  not_fact_checkable: { label: 'Не проверяется как факт', markdown: '🔵 NOT FACT CHECKABLE', tone: 'neutral', icon: 'sparkle' },
  conflicting: { label: 'Источники расходятся', markdown: '🟡 CONFLICTING', tone: 'warning', icon: 'split' },
};

const STANCES = {
  supports: { label: 'Подтверждает', tone: 'positive' },
  contradicts: { label: 'Противоречит', tone: 'negative' },
  neutral: { label: 'Контекст', tone: 'neutral' },
  insufficient: { label: 'Недостаточно', tone: 'warning' },
};

const EVIDENCE_SUFFICIENCY = {
  direct: { label: 'Прямое доказательство', shortLabel: 'DIRECT', description: 'Источник прямо подтверждает или опровергает claim.', tone: 'direct' },
  combined: { label: 'Комбинация источников', shortLabel: 'COMBINED', description: 'Вывод получен из нескольких связанных источников или предпосылок.', tone: 'combined' },
  indirect: { label: 'Косвенное доказательство', shortLabel: 'INDIRECT', description: 'Доказательства связаны с claim косвенно и требуют осторожной интерпретации.', tone: 'indirect' },
  insufficient: { label: 'Недостаточно доказательств', shortLabel: 'INSUFFICIENT', description: 'Доказательств недостаточно — claim получает статус UNVERIFIED.', tone: 'insufficient' },
};

const PROCESS_STEPS = [
  ['layers', 'Выделяем атомарные claims'],
  ['search', 'Ищем независимые источники'],
  ['source', 'Сверяем доказательства'],
  ['shield', 'Собираем объяснимый отчёт'],
];

function normalizeAnalysis(payload) {
  const claims = Array.isArray(payload?.claims) ? payload.claims : [];
  const summary = payload?.summary || {};
  const score = Number(summary.verification_score ?? summary.score ?? 0);
  return {
    ...payload,
    summary: {
      total_claims: summary.total_claims ?? claims.length,
      supported: summary.supported ?? 0,
      contradicted: summary.contradicted ?? 0,
      partially_supported: summary.partially_supported ?? 0,
      unverified: summary.unverified ?? 0,
      not_fact_checkable: summary.not_fact_checkable ?? 0,
      conflicting: summary.conflicting ?? 0,
      verification_score: score > 1 ? score / 100 : score,
    },
    claims: claims.map((claim, index) => ({
      ...claim,
      id: claim.id ?? index + 1,
      verdict: String(claim.verdict || 'unverified').toLowerCase(),
      confidence: Number(claim.confidence ?? 0),
      evidence_sufficiency: String(claim.evidence_sufficiency || (String(claim.verdict || '').toLowerCase() === 'unverified' ? 'INSUFFICIENT' : 'DIRECT')).toLowerCase(),
      sources: Array.isArray(claim.sources) ? claim.sources.map((source) => ({ ...source, stance: String(source.stance || 'NEUTRAL').toLowerCase() })) : [],
    })),
  };
}

function Icon({ name, size = 20, stroke = 1.8 }) {
  const props = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: stroke, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true };
  const paths = {
    arrow: <><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>, check: <path d="m5 12 4.2 4.2L19 6.5" />, close: <><path d="m7 7 10 10M17 7 7 17" /></>,
    half: <><path d="M12 3a9 9 0 1 0 0 18V3Z" /><path d="M12 3a9 9 0 0 1 0 18" /></>, question: <><circle cx="12" cy="12" r="9" /><path d="M9.75 9a2.35 2.35 0 1 1 4.34 1.26c-.9 1.1-2.09 1.31-2.09 2.74" /><path d="M12 16.8h.01" /></>,
    sparkle: <><path d="m12 3-1.1 4.4L7 8.5l3.9 1.1L12 14l1.1-4.4L17 8.5l-3.9-1.1L12 3Z" /><path d="m19 15-.5 2-2 .5 2 .5.5 2 .5-2 2-.5-2-.5-.5-2Z" /></>,
    split: <><path d="M7 4v3c0 2.2 1.8 4 4 4h6" /><path d="m14 8 3 3-3 3" /><path d="M7 20v-3c0-2.2 1.8-4 4-4h6" /><path d="m14 12 3 3-3 3" /></>,
    shield: <path d="M12 3.4 19 6v5.2c0 4.5-2.8 7.9-7 9.4-4.2-1.5-7-4.9-7-9.4V6l7-2.6Z" />, search: <><circle cx="10.8" cy="10.8" r="5.7" /><path d="m15 15 4.4 4.4" /></>,
    layers: <><path d="m12 3 8.5 4.5L12 12 3.5 7.5 12 3Z" /><path d="m3.5 12 8.5 4.5 8.5-4.5" /><path d="m3.5 16.5 8.5 4.5 8.5-4.5" /></>,
    source: <><path d="M14 4h-4a4 4 0 0 0 0 8h1" /><path d="M10 20h4a4 4 0 1 0 0-8h-1" /><path d="m9 12 6 0" /></>, menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>, x: <><path d="m6 6 12 12M18 6 6 18" /></>,
    reset: <><path d="M20 11a8 8 0 1 0 2 5.5" /><path d="M20 4v7h-7" /></>, external: <><path d="M14 5h5v5" /><path d="m19 5-8 8" /><path d="M18 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></>,
    chevron: <path d="m7 10 5 5 5-5" />, copy: <><rect x="8" y="8" width="11" height="11" rx="2" /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0 2 2v8a2 2 0 0 0 2 2h2" /></>,
    download: <><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M5 20h14" /></>, info: <><circle cx="12" cy="12" r="9" /><path d="M12 10v5" /><path d="M12 7.5h.01" /></>,
    send: <><path d="m20 4-7.6 16-2.6-6.8L3 10.6 20 4Z" /><path d="m9.8 13.2 4-4" /></>, clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3.2 2" /></>, quote: <path d="M7 9H4v4h4v-2H6.5c0-1.3.8-2 2-2V7c-1 0-1.5.5-1.5 2Zm9 0h-3v4h4v-2h-1.5c0-1.3.8-2 2-2V7c-1 0-1.5.5-1.5 2Z" />,
    report: <><path d="M7 3h7l4 4v14H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" /><path d="M14 3v5h5M9 13h6M9 17h4" /></>, target: <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2" /></>,
  };
  return <svg {...props}>{paths[name] || paths.sparkle}</svg>;
}

function Brand() { return <a className="brand" href="#top" aria-label="Senim AI — на главную"><span className="brand-mark"><Icon name="shield" size={18} stroke={2.1} /></span><span>Senim <span>AI</span></span></a>; }

function StatusPill({ verdict, compact = false }) {
  const status = VERDICTS[verdict] || VERDICTS.unverified;
  return <span className={`status-pill ${status.tone} ${compact ? 'compact' : ''}`}><span className="pill-symbol"><Icon name={status.icon} size={compact ? 12 : 14} stroke={2.4} /></span>{status.label}</span>;
}

function EvidenceBadge({ sufficiency, compact = false }) {
  const evidence = EVIDENCE_SUFFICIENCY[String(sufficiency || 'insufficient').toLowerCase()] || EVIDENCE_SUFFICIENCY.insufficient;
  return <span className={`evidence-badge ${evidence.tone} ${compact ? 'compact' : ''}`} title={evidence.description}><Icon name="source" size={compact ? 12 : 14} stroke={2.15} /><span>{compact ? evidence.shortLabel : evidence.label}</span></span>;
}

function ScoreRing({ score }) {
  const percent = Math.round(score * 100);
  const color = percent >= 75 ? 'var(--green)' : percent >= 45 ? 'var(--amber)' : 'var(--red)';
  return <div className="score-ring" style={{ '--score': `${percent * 3.6}deg`, '--ring-color': color }}><div className="score-core"><strong>{percent}<small>%</small></strong><span>trust score</span></div></div>;
}

function getWhySteps(value) {
  if (Array.isArray(value)) return value.map((step) => typeof step === 'string' ? step : step?.text || step?.description).filter(Boolean);
  if (typeof value === 'string' && value.trim()) return value.split(/\n+/).map((step) => step.replace(/^\d+[.)]\s*/, '')).filter(Boolean);
  if (value?.steps) return getWhySteps(value.steps);
  return [];
}

function formatDuration(value) { return typeof value === 'number' && Number.isFinite(value) ? `${(value / 1000).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} сек` : null; }
function formatDate(value) { try { return value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : null; } catch { return null; } }

function findRange(claim, originalText) {
  const start = Number(claim.start_char);
  const end = Number(claim.end_char);
  if (Number.isInteger(start) && Number.isInteger(end) && start >= 0 && end > start && originalText.slice(start, end).trim()) return { start, end };
  if (claim.original_quote) { const found = originalText.indexOf(claim.original_quote); if (found >= 0) return { start: found, end: found + claim.original_quote.length }; }
  return null;
}

function HighlightedText({ originalText, claims }) {
  const ranges = claims.map((claim) => ({ claim, range: findRange(claim, originalText) })).filter((item) => item.range).sort((a, b) => a.range.start - b.range.start);
  const parts = [];
  let cursor = 0;
  ranges.forEach(({ claim, range }) => {
    if (range.start < cursor) return;
    if (range.start > cursor) parts.push(<span key={`plain-${cursor}`}>{originalText.slice(cursor, range.start)}</span>);
    parts.push(<button type="button" className={`highlight-token ${VERDICTS[claim.verdict]?.tone || 'neutral'}`} onClick={() => document.getElementById(`claim-${claim.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })} key={`claim-${claim.id}`} title="Открыть проверку claim"><span>{originalText.slice(range.start, range.end)}</span><sup>{claim.id}</sup></button>);
    cursor = range.end;
  });
  if (cursor < originalText.length) parts.push(<span key="plain-end">{originalText.slice(cursor)}</span>);
  return <p className="highlighted-answer">{parts.length ? parts : originalText}</p>;
}

function markdownReport(result, originalText) {
  const lines = ['# Senim AI — отчёт о проверке', '', `**Анализ:** \`${result.analysis_id || 'analysis'}\``, result.timestamp ? `**Время:** ${formatDate(result.timestamp)}` : '', result.processing_time_ms ? `**Обработка:** ${formatDuration(result.processing_time_ms)}` : '', '', '## Исходный ответ AI', '', `> ${originalText.replace(/\n/g, '\n> ')}`, '', `## Итог — ${Math.round(result.summary.verification_score * 100)}% trust score`, ''];
  result.claims.forEach((claim) => {
    const verdict = VERDICTS[claim.verdict] || VERDICTS.unverified;
    const evidence = EVIDENCE_SUFFICIENCY[claim.evidence_sufficiency] || EVIDENCE_SUFFICIENCY.insufficient;
    lines.push(`### ${verdict.markdown}`, '', `**Claim ${claim.id}:** ${claim.text}`, claim.original_quote ? `> Фрагмент: “${claim.original_quote}”` : '', '', `**Доказательная достаточность:** ${evidence.shortLabel} — ${evidence.label}.`, '', `**Объяснение:** ${claim.explanation || 'Не предоставлено.'}`, '');
    const steps = getWhySteps(claim.why_verdict);
    if (steps.length) { lines.push('**Почему такой вердикт:**'); steps.forEach((step, index) => lines.push(`${index + 1}. ${step}`)); lines.push(''); }
    if (claim.sources?.length) { lines.push('**Источники:**'); claim.sources.forEach((source) => lines.push(`- [${source.title || source.domain}](${source.url}) — **${String(source.stance || 'NEUTRAL').toUpperCase()}**${source.snippet ? `: ${source.snippet}` : ''}`)); lines.push(''); }
  });
  lines.push('---', 'Senim AI показывает доказательства и объяснение, но оставляет решение пользователю.');
  return lines.filter((line, index, all) => !(line === '' && all[index - 1] === '')).join('\n');
}

function ReportActions({ result, originalText }) {
  const [notice, setNotice] = useState('');
  const report = useMemo(() => markdownReport(result, originalText), [result, originalText]);
  async function copyReport() {
    try { await navigator.clipboard.writeText(report); setNotice('Отчёт скопирован'); } catch { setNotice('Не удалось скопировать — попробуйте скачать'); }
    window.setTimeout(() => setNotice(''), 2400);
  }
  function downloadReport() {
    const url = URL.createObjectURL(new Blob([report], { type: 'text/markdown;charset=utf-8' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `senim-ai-report-${result.analysis_id || 'analysis'}.md`; anchor.click(); URL.revokeObjectURL(url);
    setNotice('Markdown скачан'); window.setTimeout(() => setNotice(''), 2400);
  }
  return <div className="report-actions"><button className="report-button" onClick={copyReport}><Icon name="copy" size={15} /> Скопировать</button><button className="report-button primary" onClick={downloadReport}><Icon name="download" size={16} /> Скачать .md</button>{notice && <span className="action-notice">{notice}</span>}</div>;
}

function HeroWorkspace({ text, setText, mode, setMode, status, error, handleAnalyze, useExample, isLiveAvailable }) {
  const focusAnalyzer = () => {
    const input = document.getElementById('ai-answer');
    input?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    window.setTimeout(() => input?.focus({ preventScroll: true }), 480);
  };
  return <section className="hero hero-focused" id="demo"><div className="hero-vista" /><div className="hero-glow" />
    <div className="hero-copy"><h1>Проверяйте ответы AI<br /><em>с доказательствами.</em></h1><p className="hero-lede">Senim AI находит конкретные утверждения, сопоставляет их с независимыми источниками и показывает, почему им можно или нельзя доверять.</p><div className="hero-actions"><button className="hero-primary" onClick={focusAnalyzer}>Начать проверку <Icon name="arrow" size={17} /></button><a href="#how" className="hero-secondary"><Icon name="shield" size={15} /> Как это работает</a></div></div>
    <div className="proof-workspace"><div className="workspace-top"><div className="workspace-title"><span className="workspace-dot" /> Проверка ответа</div><div className="mode-switch" aria-label="Режим проверки"><span>Режим</span><button className={mode === 'demo' ? 'active' : ''} onClick={() => setMode('demo')}>Демо</button><button className={mode === 'live' ? 'active' : ''} onClick={() => setMode('live')} disabled={!isLiveAvailable} title={isLiveAvailable ? 'Подключённый FastAPI' : 'Подключите VITE_API_BASE_URL, чтобы включить Live API'}>Live API</button></div></div>
      <form id="analyze-form" onSubmit={handleAnalyze}><label className="sr-only" htmlFor="ai-answer">Ответ ИИ для проверки</label><div className={`workspace-input ${error ? 'has-error' : ''}`}><div className="input-caption"><span>Вставьте ответ AI</span><span>{text.length.toLocaleString('ru-RU')} / 20 000</span></div><textarea id="ai-answer" value={text} onChange={(event) => setText(event.target.value)} maxLength={20000} placeholder="Вставьте текст, который хотите проверить…" /></div>{error && <p className="form-error"><Icon name="info" size={16} /> {error}</p>}<div className="workspace-bottom"><span><Icon name="shield" size={15} /> {mode === 'demo' ? 'Проверим на готовом примере без API' : 'Отправим текст в подключённый FastAPI'}</span><button className="analyze-button" disabled={status === 'loading'}>{status === 'loading' ? <><i className="button-spinner" /> Ищем доказательства</> : <>Проверить ответ <Icon name="arrow" size={18} /></>}</button></div></form>
      <div className="workspace-examples"><span>Примеры:</span><button onClick={() => useExample(STARTER_TEXT)}>Ошибка в факте</button><button onClick={() => useExample('Первый человек высадился на Марсе в 1969 году.')}>Галлюцинация</button><button onClick={() => useExample('Python был создан Гвидо ван Россумом в 1991 году.')}>Верный факт</button></div>
    </div>
  </section>;
}

function AnalysisLoader({ currentStep }) { return <section className="analysis-loader result-section" aria-live="polite"><div className="loader-orbit"><div className="loader-logo"><Icon name="shield" size={28} stroke={2.2} /></div><i /><i /><i /></div><p className="eyebrow">Senim AI работает</p><h2>Собираем доказательства, а не догадки.</h2><p className="loader-caption">Разбираем ответ на отдельные claims, ищем источники и строим объяснение для каждого вывода.</p><ol className="process-list">{PROCESS_STEPS.map(([icon, label], index) => <li className={index < currentStep ? 'complete' : index === currentStep ? 'active' : ''} key={label}><span>{index < currentStep ? <Icon name="check" size={15} stroke={2.8} /> : <Icon name={icon} size={16} />}</span><b>{label}</b><em>{index < currentStep ? 'Готово' : index === currentStep ? 'В процессе' : 'Далее'}</em></li>)}</ol><div className="loader-note"><Icon name="shield" size={15} /> Внешний контент считается данными, а не инструкциями.</div></section>; }

function AnalysisSummary({ result, sourceText, onNewAnalysis }) {
  const summary = result.summary;
  const needsReview = summary.contradicted + summary.partially_supported + summary.conflicting + summary.unverified > 0;
  const metrics = [['supported', summary.supported, 'Подтверждено'], ['contradicted', summary.contradicted, 'Опровергнуто'], ['partially_supported', summary.partially_supported, 'Частично'], ['unverified', summary.unverified + summary.conflicting, 'Неясно']].filter(([, value]) => value > 0);
  return <section className="summary-card result-section" aria-labelledby="result-title"><div className="summary-main"><div className="summary-copy"><div className="section-kicker"><span className="live-dot" /> Анализ завершён <span className="analysis-id">#{result.analysis_id || 'analysis'}</span></div><h2 id="result-title">{needsReview ? 'Ответ требует внимания' : 'Ответ выглядит надёжным'}</h2><p>{needsReview ? 'Мы нашли конкретные места, где ответ расходится с доказательствами или требует контекста.' : 'Все найденные утверждения получили достаточное подтверждение из внешних источников.'}</p><div className="analysis-meta">{result.processing_time_ms && <span><Icon name="clock" size={14} /> {formatDuration(result.processing_time_ms)}</span>}{result.timestamp && <span><Icon name="target" size={14} /> {formatDate(result.timestamp)}</span>}</div></div><ScoreRing score={summary.verification_score} /></div><div className="metric-grid">{metrics.map(([verdict, value, label]) => <div className={`metric ${VERDICTS[verdict].tone}`} key={verdict}><span>{value}</span><small>{label}</small></div>)}<div className="metric total"><span>{summary.total_claims}</span><small>всего claims</small></div></div><div className="summary-footer"><span><Icon name="info" size={16} /> Скор — ориентир. Источники и контекст важнее одного числа.</span><div><ReportActions result={result} originalText={sourceText} /><button className="text-button" onClick={onNewAnalysis}><Icon name="reset" size={16} /> Новый анализ</button></div></div></section>;
}

function OriginalTextPanel({ sourceText, claims }) { return <section className="original-text result-section" aria-labelledby="original-text-title"><div className="original-head"><div><p className="eyebrow">Claim highlighting</p><h2 id="original-text-title">Где именно ответ <em>теряет доверие</em></h2></div><div className="highlight-legend"><span className="positive"><i /> Подтверждено</span><span className="warning"><i /> Частично</span><span className="negative"><i /> Опровергнуто</span></div></div><div className="answer-sheet"><div className="answer-sheet-top"><span><Icon name="quote" size={15} /> Исходный ответ AI</span><small>Нажмите на фрагмент, чтобы открыть его разбор</small></div><HighlightedText originalText={sourceText} claims={claims} /></div></section>; }

function SourceCard({ source }) { const initial = (source.domain || source.title || '?').replace(/^www\./, '').charAt(0).toUpperCase(); const stance = STANCES[source.stance] || STANCES.neutral; return <a className="source-card" href={source.url} target="_blank" rel="noreferrer"><span className="source-letter">{initial}</span><span className="source-content"><span className="source-meta"><b>{source.domain || 'Источник'}</b><span><em>{source.quality || 'Источник'}</em><em className={`stance ${stance.tone}`}>{stance.label}</em></span></span><strong>{source.title || 'Открыть источник'}</strong>{source.snippet && <small>“{source.snippet}”</small>}<span className="source-bottom"><span><Icon name="clock" size={12} /> {source.freshness || 'Проверено при анализе'}</span><span>Открыть <Icon name="external" size={13} /></span></span></span></a>; }

function AskWhy({ claim }) { const steps = getWhySteps(claim.why_verdict); const evidence = EVIDENCE_SUFFICIENCY[claim.evidence_sufficiency] || EVIDENCE_SUFFICIENCY.insufficient; return <div className="claim-explainability"><div className={`evidence-panel ${evidence.tone}`}><div><span className="detail-label"><Icon name="source" size={16} /> Доказательная достаточность</span><p>{evidence.description}</p></div><EvidenceBadge sufficiency={claim.evidence_sufficiency} /></div>{steps.length > 0 && <div className="why-panel"><div className="why-title"><span><Icon name="target" size={16} /> Ask Why</span><small>цепочка проверки</small></div><ol>{steps.map((step, index) => <li key={`${claim.id}-${index}`}><span>{String(index + 1).padStart(2, '0')}</span><p>{step}</p></li>)}</ol></div>}</div>; }

function ClaimCard({ claim, open, onToggle, index }) {
  const status = VERDICTS[claim.verdict] || VERDICTS.unverified;
  const confidence = Math.round((claim.confidence > 1 ? claim.confidence / 100 : claim.confidence) * 100);
  return <article id={`claim-${claim.id}`} className={`claim-card ${status.tone} ${open ? 'expanded' : ''}`} style={{ '--delay': `${index * 80}ms` }}><button className="claim-top" onClick={onToggle} aria-expanded={open} aria-controls={`claim-detail-${claim.id}`}><span className="claim-number">{String(claim.id).padStart(2, '0')}</span><span className="claim-question"><span className="claim-type">{claim.type === 'temporal' ? 'Время' : claim.type === 'numerical' ? 'Число' : claim.type === 'comparative' ? 'Сравнение' : 'Факт'}</span><strong>{claim.text}</strong>{claim.original_quote && <small><Icon name="quote" size={12} /> “{claim.original_quote}”</small>}</span><span className="claim-verdict"><StatusPill verdict={claim.verdict} compact /><span className="claim-confidence">{confidence}% уверенность</span></span><span className="expand-icon"><Icon name="chevron" size={19} /></span></button><div id={`claim-detail-${claim.id}`} className="claim-detail" hidden={!open}><div className="detail-grid"><div className="reason"><span className="detail-label"><Icon name="sparkle" size={16} /> Коротко</span><p>{claim.explanation || 'Объяснение пока недоступно.'}</p><div className="confidence-bar"><span>Уверенность</span><div><i style={{ width: `${confidence}%` }} /></div><b>{confidence}%</b></div></div><div className="claim-facts"><span className="detail-label"><Icon name="layers" size={16} /> Проверка</span><p>Claim выделен из исходного текста, сопоставлен с внешними доказательствами и получил объяснимый verdict.</p><div className="fact-tags"><span>Atomic claim</span><span>Evidence-based</span><span>Explainable</span></div></div></div><AskWhy claim={claim} /><div className="sources-heading"><span><Icon name="source" size={18} /> Источники и их позиция</span><b>{claim.sources.length} {claim.sources.length === 1 ? 'источник' : 'источника'}</b></div><div className="sources-list">{claim.sources.length ? claim.sources.map((source, sourceIndex) => <SourceCard source={source} key={`${source.url}-${sourceIndex}`} />) : <p className="empty-sources">Для этого утверждения пока не найдено достаточно надёжных источников.</p>}</div></div></article>;
}

function ClaimResults({ result }) { const [openClaim, setOpenClaim] = useState(result.claims[0]?.id); useEffect(() => setOpenClaim(result.claims[0]?.id), [result]); return <section className="claims-section result-section" id="claims" aria-labelledby="claims-title"><div className="claims-heading"><div><p className="eyebrow">Evidence map</p><h2 id="claims-title">Каждое утверждение — <em>отдельно.</em></h2><p>Вместо общего «верю / не верю» — точная карта доказательств для каждого факта.</p></div><span className="claims-count"><Icon name="layers" size={17} /> {result.claims.length} claims</span></div><div className="claims-list">{result.claims.map((claim, index) => <ClaimCard claim={claim} key={claim.id} index={index} open={openClaim === claim.id} onToggle={() => setOpenClaim(openClaim === claim.id ? null : claim.id)} />)}</div></section>; }

function Principles() { return <section className="principles" id="how"><div className="principles-top"><p className="eyebrow">Почему это работает</p><h2>Не угадываем правду.<br /><em>Показываем путь к ней.</em></h2><p>LLM не является источником истины: он помогает сравнить claim с внешними доказательствами и открыто объяснить свой вывод.</p></div><div className="principle-grid"><article><span className="principle-icon"><Icon name="layers" size={23} /></span><strong>Atomic claims</strong><p>Разделяем длинный ответ на независимые, проверяемые кусочки.</p></article><article><span className="principle-icon"><Icon name="source" size={23} /></span><strong>Source stance</strong><p>Видно не только ссылку, но и то, подтверждает ли она claim.</p></article><article><span className="principle-icon"><Icon name="shield" size={23} /></span><strong>Evidence strength</strong><p>DIRECT, COMBINED, INDIRECT или INSUFFICIENT — без скрытых допущений.</p></article><article><span className="principle-icon"><Icon name="target" size={23} /></span><strong>Ask Why</strong><p>Пошаговая логика проверки делает verdict понятным и проверяемым.</p></article></div></section>; }

function App() {
  const [text, setText] = useState(STARTER_TEXT);
  const [analysisInput, setAnalysisInput] = useState(STARTER_TEXT);
  const [mode, setMode] = useState('demo');
  const [status, setStatus] = useState('idle');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [step, setStep] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const isLiveAvailable = Boolean(API_BASE);
  const scoreText = result ? `${Math.round(result.summary.verification_score * 100)}%` : null;

  useEffect(() => { if (status !== 'loading') return undefined; setStep(0); const timer = window.setInterval(() => setStep((current) => Math.min(current + 1, PROCESS_STEPS.length - 1)), 720); return () => window.clearInterval(timer); }, [status]);

  async function handleAnalyze(event) {
    event?.preventDefault();
    if (!text.trim()) { setError('Вставьте ответ ИИ, который хотите проверить.'); return; }
    if (text.length > 20000) { setError('Для одного анализа доступно до 20 000 символов.'); return; }
    setError(''); setStatus('loading'); setResult(null); setAnalysisInput(text.trim());
    try {
      let payload;
      if (mode === 'live') { const response = await fetch(`${API_BASE}/api/v1/analyze`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, language: 'ru', max_claims: 8 }) }); if (!response.ok) throw new Error(`Сервис вернул ошибку ${response.status}`); payload = await response.json(); }
      else { await new Promise((resolve) => window.setTimeout(resolve, 2250)); payload = DEMO_ANALYSIS; }
      setResult(normalizeAnalysis(payload)); setStatus('result'); window.setTimeout(() => document.getElementById('result-area')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
    } catch (requestError) { setStatus('idle'); setError(`${requestError.message || 'Не удалось выполнить проверку.'} Проверьте подключение к API или включите демо-режим.`); }
  }
  function useExample(nextText) { setText(nextText); setResult(null); setStatus('idle'); setError(''); }
  function reset() { setResult(null); setStatus('idle'); setError(''); window.scrollTo({ top: 0, behavior: 'smooth' }); }

  return <div id="top" className="app-shell"><header className="site-header"><div className="nav-wrap"><Brand /><nav className={menuOpen ? 'open' : ''} aria-label="Главная навигация"><a href="#how" onClick={() => setMenuOpen(false)}>Как работает</a><a href="#claims" onClick={() => setMenuOpen(false)}>Доказательства</a><a href="#demo" onClick={() => setMenuOpen(false)}>Попробовать</a></nav><div className="nav-actions"><button className="nav-cta" onClick={() => document.getElementById('analyze-form')?.scrollIntoView({ behavior: 'smooth', block: 'center' })}>Проверить ответ <Icon name="arrow" size={16} /></button><button className="menu-button" aria-label={menuOpen ? 'Закрыть меню' : 'Открыть меню'} aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}><Icon name={menuOpen ? 'x' : 'menu'} size={22} /></button></div></div></header><main><HeroWorkspace text={text} setText={setText} mode={mode} setMode={setMode} status={status} error={error} handleAnalyze={handleAnalyze} useExample={useExample} isLiveAvailable={isLiveAvailable} /><Principles /><div id="result-area" className="result-area">{status === 'loading' && <AnalysisLoader currentStep={step} />}{status === 'result' && result && <><AnalysisSummary result={result} sourceText={analysisInput} onNewAnalysis={reset} /><OriginalTextPanel sourceText={analysisInput} claims={result.claims} /><ClaimResults result={result} /><section className="result-cta result-section"><div><p className="eyebrow">Ваша проверка</p><h2>Senim AI показывает доказательства.<br /><em>Решение остаётся за вами.</em></h2></div><button className="outline-button" onClick={reset}>Проверить другой ответ <Icon name="arrow" size={18} /></button></section></>}</div></main><footer><Brand /><p>Проверка ответов AI на основе доказательств.</p><span>Built for WIT Teens Challenge Hackathon</span></footer>{scoreText && <div className="mobile-result-chip" role="status"><span className="live-dot" /> Анализ готов: {scoreText}</div>}</div>;
}

export default App;
