import { useEffect, useMemo, useState } from 'react';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

const STARTER_TEXT = `Эйфелева башня была построена в 1889 году и находится в Лондоне. Её высота составляет 324 метра, а в 2024 году она оставалась самым высоким сооружением в мире.`;

const DEMO_ANALYSIS = {
  analysis_id: 'senim-eiffel-2026',
  summary: {
    total_claims: 4,
    supported: 1,
    contradicted: 2,
    partially_supported: 1,
    unverified: 0,
    not_fact_checkable: 0,
    conflicting: 0,
    verification_score: 0.38,
  },
  claims: [
    {
      id: 1,
      type: 'temporal',
      verdict: 'partially_supported',
      confidence: 0.98,
      text: 'Эйфелева башня была построена в 1889 году.',
      explanation:
        'Официальный сайт башни и справочные источники указывают, что строительство завершилось к Всемирной выставке 1889 года в Париже.',
      sources: [
        {
          title: 'The Eiffel Tower: history and key dates',
          domain: 'toureiffel.paris',
          url: 'https://www.toureiffel.paris/en/the-monument/history',
          snippet: 'The Eiffel Tower was inaugurated on 31 March 1889 for the Universal Exhibition.',
          quality: 'Primary source',
          freshness: 'Official reference',
        },
      ],
    },
    {
      id: 2,
      type: 'factual',
      verdict: 'contradicted',
      confidence: 0.99,
      text: 'Эйфелева башня находится в Лондоне.',
      explanation:
        'Надёжные источники единодушно размещают Эйфелеву башню на Марсовом поле в Париже, Франция. Утверждение о Лондоне противоречит доказательствам.',
      sources: [
        {
          title: 'Eiffel Tower — official visitor information',
          domain: 'toureiffel.paris',
          url: 'https://www.toureiffel.paris/en',
          snippet: 'The Eiffel Tower stands on the Champ de Mars in Paris, France.',
          quality: 'Primary source',
          freshness: 'Official reference',
        },
        {
          title: 'Eiffel Tower',
          domain: 'britannica.com',
          url: 'https://www.britannica.com/topic/Eiffel-Tower-Paris-France',
          snippet: 'Landmark of Paris, located on the Champ de Mars on the left bank of the Seine.',
          quality: 'Reference',
          freshness: 'Reviewed reference',
        },
      ],
    },
    {
      id: 3,
      type: 'numerical',
      verdict: 'supported',
      confidence: 0.96,
      text: 'Высота Эйфелевой башни составляет 324 метра.',
      explanation:
        'Официальный источник указывает высоту башни 330 метров вместе с антеннами; высота 324 метра использовалась в ряде описаний до обновления антенны. Формулировка в целом подтверждается, но для точности стоит указывать дату измерения.',
      sources: [
        {
          title: 'The Eiffel Tower in figures',
          domain: 'toureiffel.paris',
          url: 'https://www.toureiffel.paris/en/the-monument/key-figures',
          snippet: 'Today, the Eiffel Tower is 330 metres high, including its antennas.',
          quality: 'Primary source',
          freshness: 'Official reference',
        },
      ],
    },
    {
      id: 4,
      type: 'comparative',
      verdict: 'contradicted',
      confidence: 0.99,
      text: 'В 2024 году Эйфелева башня оставалась самым высоким сооружением в мире.',
      explanation:
        'Это утверждение противоречит данным о Burj Khalifa: его высота 828 метров, что существенно больше высоты Эйфелевой башни.',
      sources: [
        {
          title: 'Burj Khalifa facts and figures',
          domain: 'burjkhalifa.ae',
          url: 'https://www.burjkhalifa.ae/en/the-tower/facts-figures/',
          snippet: 'At 828 metres, Burj Khalifa has been the tallest building in the world since 2010.',
          quality: 'Primary source',
          freshness: 'Official reference',
        },
      ],
    },
  ],
};

const VERDICTS = {
  supported: { label: 'Подтверждено', description: 'Доказательства поддерживают утверждение', tone: 'positive', icon: 'check' },
  contradicted: { label: 'Опровергнуто', description: 'Доказательства ему противоречат', tone: 'negative', icon: 'close' },
  partially_supported: { label: 'Частично подтверждено', description: 'Верна только часть утверждения', tone: 'warning', icon: 'half' },
  unverified: { label: 'Недостаточно данных', description: 'Доказательств пока недостаточно', tone: 'neutral', icon: 'question' },
  not_fact_checkable: { label: 'Не проверяется как факт', description: 'Это мнение или субъективная оценка', tone: 'neutral', icon: 'sparkle' },
  conflicting: { label: 'Источники расходятся', description: 'Надёжные источники дают разные данные', tone: 'warning', icon: 'split' },
};

const PROCESS_STEPS = [
  ['split', 'Выделяем атомарные утверждения'],
  ['search', 'Ищем независимые источники'],
  ['evidence', 'Сопоставляем доказательства'],
  ['verdict', 'Собираем прозрачный отчёт'],
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
      sources: Array.isArray(claim.sources) ? claim.sources : [],
    })),
  };
}

function Icon({ name, size = 20, stroke = 1.8 }) {
  const props = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: stroke, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true };
  const paths = {
    arrow: <><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>,
    check: <path d="m5 12 4.2 4.2L19 6.5" />,
    close: <><path d="m7 7 10 10M17 7 7 17" /></>,
    half: <><path d="M12 3a9 9 0 1 0 0 18V3Z" /><path d="M12 3a9 9 0 0 1 0 18" /></>,
    question: <><circle cx="12" cy="12" r="9" /><path d="M9.75 9a2.35 2.35 0 1 1 4.34 1.26c-.9 1.1-2.09 1.31-2.09 2.74" /><path d="M12 16.8h.01" /></>,
    sparkle: <><path d="m12 3-1.1 4.4L7 8.5l3.9 1.1L12 14l1.1-4.4L17 8.5l-3.9-1.1L12 3Z" /><path d="m19 15-.5 2-2 .5 2 .5.5 2 .5-2 2-.5-2-.5-.5-2Z" /><path d="m5 15-.5 2-2 .5 2 .5.5 2 .5-2 2-.5-2-.5-.5-2Z" /></>,
    split: <><path d="M7 4v3c0 2.2 1.8 4 4 4h6" /><path d="m14 8 3 3-3 3" /><path d="M7 20v-3c0-2.2 1.8-4 4-4h6" /><path d="m14 12 3 3-3 3" /></>,
    shield: <path d="M12 3.4 19 6v5.2c0 4.5-2.8 7.9-7 9.4-4.2-1.5-7-4.9-7-9.4V6l7-2.6Z" />,
    search: <><circle cx="10.8" cy="10.8" r="5.7" /><path d="m15 15 4.4 4.4" /></>,
    layers: <><path d="m12 3 8.5 4.5L12 12 3.5 7.5 12 3Z" /><path d="m3.5 12 8.5 4.5 8.5-4.5" /><path d="m3.5 16.5 8.5 4.5 8.5-4.5" /></>,
    source: <><path d="M14 4h-4a4 4 0 0 0 0 8h1" /><path d="M10 20h4a4 4 0 1 0 0-8h-1" /><path d="m9 12 6 0" /></>,
    menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
    x: <><path d="m6 6 12 12M18 6 6 18" /></>,
    reset: <><path d="M20 11a8 8 0 1 0 2 5.5" /><path d="M20 4v7h-7" /></>,
    external: <><path d="M14 5h5v5" /><path d="m19 5-8 8" /><path d="M18 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></>,
    chevron: <path d="m7 10 5 5 5-5" />,
    copy: <><rect x="8" y="8" width="11" height="11" rx="2" /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" /></>,
    info: <><circle cx="12" cy="12" r="9" /><path d="M12 10v5" /><path d="M12 7.5h.01" /></>,
    send: <><path d="m20 4-7.6 16-2.6-6.8L3 10.6 20 4Z" /><path d="m9.8 13.2 4-4" /></>,
    clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3.2 2" /></>,
  };
  return <svg {...props}>{paths[name] || paths.sparkle}</svg>;
}

function Brand() {
  return <a className="brand" href="#top" aria-label="Senim AI — на главную"><span className="brand-mark"><Icon name="shield" size={19} stroke={2} /></span><span>Senim <span>AI</span></span></a>;
}

function StatusPill({ verdict, compact = false }) {
  const status = VERDICTS[verdict] || VERDICTS.unverified;
  return <span className={`status-pill ${status.tone} ${compact ? 'compact' : ''}`}><span className="pill-symbol"><Icon name={status.icon} size={compact ? 13 : 15} stroke={2.3} /></span>{status.label}</span>;
}

function ScoreRing({ score }) {
  const percent = Math.round(score * 100);
  const color = percent >= 75 ? 'var(--green)' : percent >= 45 ? 'var(--amber)' : 'var(--red)';
  return <div className="score-ring" style={{ '--score': `${percent * 3.6}deg`, '--ring-color': color }}><div className="score-core"><strong>{percent}<small>%</small></strong><span>проверено</span></div></div>;
}

function HeroVisual() {
  return <div className="hero-visual" aria-hidden="true">
    <div className="orb orb-one" /><div className="orb orb-two" /><div className="orb orb-three" />
    <div className="visual-window">
      <div className="window-top"><span /><span /><span /><em>analysis://trust</em></div>
      <div className="window-lines">
        <div className="window-label"><Icon name="sparkle" size={14} /> Evidence engine</div>
        <div className="scan-line"><i /> <b>Найдено 4 утверждения</b></div>
        <div className="scan-line"><i className="green" /> <b>2 подтверждены источниками</b></div>
        <div className="scan-line"><i className="red" /> <b>2 требуют внимания</b></div>
      </div>
      <div className="window-chart"><div /><div /><div /><div /><div /><div /></div>
    </div>
    <div className="float-card source-float"><span className="mini-icon"><Icon name="source" size={15} /></span><div><b>Доказательства</b><small>3 независимых источника</small></div><span className="verified-dot"><Icon name="check" size={11} stroke={3} /></span></div>
    <div className="float-card score-float"><span className="score-mini">84</span><div><b>Trust score</b><small>прозрачный отчёт</small></div></div>
  </div>;
}

function AnalysisLoader({ currentStep }) {
  return <section className="analysis-loader result-section" aria-live="polite">
    <div className="loader-orbit"><div className="loader-logo"><Icon name="shield" size={28} stroke={2.2} /></div><i /><i /><i /></div>
    <p className="eyebrow">Проверяем ответ</p><h2>Собираем доказательства, а не догадки.</h2>
    <p className="loader-caption">Это может занять до 30 секунд — система ищет независимые источники и сверяет каждый claim.</p>
    <ol className="process-list">
      {PROCESS_STEPS.map(([icon, label], index) => <li className={index < currentStep ? 'complete' : index === currentStep ? 'active' : ''} key={label}><span>{index < currentStep ? <Icon name="check" size={15} stroke={2.8} /> : <Icon name={icon === 'split' ? 'layers' : icon === 'search' ? 'search' : icon === 'evidence' ? 'source' : 'shield'} size={16} />}</span><b>{label}</b><em>{index < currentStep ? 'Готово' : index === currentStep ? 'В процессе' : 'Далее'}</em></li>)}
    </ol>
    <div className="loader-note"><Icon name="shield" size={15} /> Внешний контент считается данными, а не инструкциями.</div>
  </section>;
}

function AnalysisSummary({ result, onNewAnalysis }) {
  const summary = result.summary;
  const score = summary.verification_score;
  const needsReview = summary.contradicted + summary.partially_supported + summary.conflicting + summary.unverified > 0;
  const metrics = [
    ['supported', summary.supported, 'Подтверждено'],
    ['contradicted', summary.contradicted, 'Опровергнуто'],
    ['partially_supported', summary.partially_supported, 'Частично'],
    ['unverified', summary.unverified + summary.conflicting, 'Неясно'],
  ].filter(([, value]) => value > 0);
  return <section className="summary-card result-section" aria-labelledby="result-title">
    <div className="summary-main"><div className="summary-copy"><div className="section-kicker"><span className="live-dot" /> Результат проверки <span className="analysis-id">#{result.analysis_id || 'analysis'}</span></div><h2 id="result-title">{needsReview ? 'Ответ требует внимания' : 'Ответ выглядит надёжным'}</h2><p>{needsReview ? 'Не все утверждения прошли проверку. Откройте карточки ниже, чтобы увидеть, где именно расходятся данные.' : 'Все найденные утверждения получили достаточное подтверждение из внешних источников.'}</p></div><ScoreRing score={score} /></div>
    <div className="metric-grid">{metrics.map(([verdict, value, label]) => <div className={`metric ${VERDICTS[verdict].tone}`} key={verdict}><span>{value}</span><small>{label}</small></div>)}<div className="metric total"><span>{summary.total_claims}</span><small>всего claims</small></div></div>
    <div className="summary-footer"><span><Icon name="info" size={16} /> Скор — ориентир, а не истина. Решение принимаете вы.</span><button className="text-button" onClick={onNewAnalysis}><Icon name="reset" size={16} /> Новый анализ</button></div>
  </section>;
}

function SourceCard({ source }) {
  const initial = (source.domain || source.title || '?').replace(/^www\./, '').charAt(0).toUpperCase();
  return <a className="source-card" href={source.url} target="_blank" rel="noreferrer"><span className="source-letter">{initial}</span><span className="source-content"><span className="source-meta"><b>{source.domain || 'Источник'}</b><em>{source.quality || 'Источник'}</em></span><strong>{source.title || 'Открыть источник'}</strong>{source.snippet && <small>“{source.snippet}”</small>}<span className="source-bottom"><span><Icon name="clock" size={12} /> {source.freshness || 'Проверено при анализе'}</span><span>Открыть <Icon name="external" size={13} /></span></span></span></a>;
}

function ClaimCard({ claim, open, onToggle, index }) {
  const status = VERDICTS[claim.verdict] || VERDICTS.unverified;
  const confidence = Math.round((claim.confidence > 1 ? claim.confidence / 100 : claim.confidence) * 100);
  return <article className={`claim-card ${status.tone} ${open ? 'expanded' : ''}`} style={{ '--delay': `${index * 80}ms` }}>
    <button className="claim-top" onClick={onToggle} aria-expanded={open} aria-controls={`claim-detail-${claim.id}`}>
      <span className="claim-number">{String(claim.id).padStart(2, '0')}</span><span className="claim-question"><span className="claim-type">{claim.type === 'temporal' ? 'Время' : claim.type === 'numerical' ? 'Число' : claim.type === 'comparative' ? 'Сравнение' : 'Факт'}</span><strong>{claim.text}</strong></span><span className="claim-verdict"><StatusPill verdict={claim.verdict} compact /><span className="claim-confidence">Уверенность {confidence}%</span></span><span className="expand-icon"><Icon name="chevron" size={19} /></span>
    </button>
    <div id={`claim-detail-${claim.id}`} className="claim-detail" hidden={!open}>
      <div className="detail-grid"><div className="reason"><span className="detail-label"><Icon name="sparkle" size={16} /> Почему такой вердикт</span><p>{claim.explanation || 'Объяснение пока недоступно.'}</p><div className="confidence-bar"><span>Уверенность системы</span><div><i style={{ width: `${confidence}%` }} /></div><b>{confidence}%</b></div></div><div className="claim-facts"><span className="detail-label"><Icon name="layers" size={16} /> Как мы проверили</span><p>Утверждение выделено отдельно, сопоставлено с независимыми источниками, а затем получило вердикт по найденным доказательствам.</p><div className="fact-tags"><span>Atomic claim</span><span>Evidence-based</span><span>Explainable</span></div></div></div>
      <div className="sources-heading"><span><Icon name="source" size={18} /> Источники и доказательства</span><b>{claim.sources.length} {claim.sources.length === 1 ? 'источник' : 'источника'}</b></div><div className="sources-list">{claim.sources.length ? claim.sources.map((source, sourceIndex) => <SourceCard source={source} key={`${source.url}-${sourceIndex}`} />) : <p className="empty-sources">Для этого утверждения пока не найдено достаточно надёжных источников.</p>}</div>
    </div>
  </article>;
}

function ClaimResults({ result }) {
  const [openClaim, setOpenClaim] = useState(result.claims[0]?.id);
  useEffect(() => setOpenClaim(result.claims[0]?.id), [result]);
  return <section className="claims-section result-section" id="claims" aria-labelledby="claims-title"><div className="claims-heading"><div><p className="eyebrow">Разбор по claims</p><h2 id="claims-title">Каждое утверждение — отдельно.</h2><p>Так вы видите не «правда или ложь», а конкретное место, где ответ заслуживает доверия или проверки.</p></div><span className="claims-count"><Icon name="layers" size={17} /> {result.claims.length} claims</span></div><div className="claims-list">{result.claims.map((claim, index) => <ClaimCard claim={claim} key={claim.id} index={index} open={openClaim === claim.id} onToggle={() => setOpenClaim(openClaim === claim.id ? null : claim.id)} />)}</div></section>;
}

function App() {
  const [text, setText] = useState(STARTER_TEXT);
  const [mode, setMode] = useState('demo');
  const [status, setStatus] = useState('idle');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [step, setStep] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const characterCount = text.length;
  const isLiveAvailable = Boolean(API_BASE);

  useEffect(() => {
    if (status !== 'loading') return undefined;
    setStep(0);
    const timer = window.setInterval(() => setStep((current) => Math.min(current + 1, PROCESS_STEPS.length - 1)), 700);
    return () => window.clearInterval(timer);
  }, [status]);

  const scoreText = useMemo(() => result ? `${Math.round(result.summary.verification_score * 100)}%` : null, [result]);

  async function handleAnalyze(event) {
    event?.preventDefault();
    if (!text.trim()) { setError('Вставьте ответ ИИ, который хотите проверить.'); return; }
    if (text.length > 20000) { setError('Для MVP можно проверить до 20 000 символов за один раз.'); return; }
    setError(''); setStatus('loading'); setResult(null);
    try {
      if (mode === 'live') {
        const response = await fetch(`${API_BASE}/api/v1/analyze`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, language: 'ru', max_claims: 8 }) });
        if (!response.ok) throw new Error(`Сервис вернул ошибку ${response.status}`);
        setResult(normalizeAnalysis(await response.json()));
      } else {
        await new Promise((resolve) => window.setTimeout(resolve, 2250));
        setResult(normalizeAnalysis(DEMO_ANALYSIS));
      }
      setStatus('result');
      window.setTimeout(() => document.getElementById('result-area')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
    } catch (requestError) {
      setStatus('idle');
      setError(`${requestError.message || 'Не удалось выполнить проверку.'} Проверьте подключение к API или переключитесь в демо-режим.`);
    }
  }

  function useExample(nextText) { setText(nextText); setResult(null); setStatus('idle'); setError(''); window.setTimeout(() => document.getElementById('analyze-form')?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 30); }
  function reset() { setResult(null); setStatus('idle'); setError(''); window.scrollTo({ top: 0, behavior: 'smooth' }); }

  return <div id="top" className="app-shell">
    <header className="site-header"><div className="nav-wrap"><Brand /><nav className={menuOpen ? 'open' : ''} aria-label="Главная навигация"><a href="#how" onClick={() => setMenuOpen(false)}>Как это работает</a><a href="#claims" onClick={() => setMenuOpen(false)}>Почему доверять</a><a href="#demo" onClick={() => setMenuOpen(false)}>Демо</a></nav><div className="nav-actions"><button className="nav-cta" onClick={() => document.getElementById('analyze-form')?.scrollIntoView({ behavior: 'smooth', block: 'center' })}>Проверить ответ <Icon name="arrow" size={16} /></button><button className="menu-button" aria-label={menuOpen ? 'Закрыть меню' : 'Открыть меню'} aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}><Icon name={menuOpen ? 'x' : 'menu'} size={22} /></button></div></div></header>
    <main>
      <section className="hero"><div className="hero-copy"><p className="hero-label"><span><Icon name="shield" size={14} stroke={2.3} /></span> Evidence-based AI verification</p><h1>Доверяйте <em>доказательствам,</em><br />а не уверенности ИИ.</h1><p className="hero-lede">Senim AI разбирает ответ ИИ на проверяемые утверждения, ищет внешние источники и объясняет, чему и почему можно доверять.</p><div className="hero-trust"><span><i><Icon name="check" size={12} stroke={3} /></i> Не решаем за вас</span><span><i><Icon name="check" size={12} stroke={3} /></i> Показываем источники</span></div></div><HeroVisual /></section>
      <section className="analyzer-card" id="demo"><div className="analyzer-intro"><div><p className="eyebrow">Проверка ответа</p><h2>Что сказал ваш AI?</h2></div><div className="mode-switch" aria-label="Режим проверки"><button className={mode === 'demo' ? 'active' : ''} onClick={() => setMode('demo')}><span /> Демо-режим</button><button className={mode === 'live' ? 'active' : ''} disabled={!isLiveAvailable} title={isLiveAvailable ? 'Отправить запрос в подключённый API' : 'Добавьте VITE_API_BASE_URL в .env, чтобы включить API'} onClick={() => setMode('live')}><span /> Live API</button></div></div>
        <form onSubmit={handleAnalyze} id="analyze-form"><label className="sr-only" htmlFor="ai-answer">Ответ ИИ для проверки</label><div className={`textarea-wrap ${error ? 'has-error' : ''}`}><div className="textarea-top"><span><Icon name="sparkle" size={15} /> Вставьте ответ ChatGPT, Gemini, Claude или другого AI</span><span>{characterCount.toLocaleString('ru-RU')} / 20 000</span></div><textarea id="ai-answer" value={text} onChange={(event) => setText(event.target.value)} placeholder="Например: ИИ сообщил, что..." maxLength={20000} /></div>{error && <p className="form-error"><Icon name="info" size={16} /> {error}</p>}<div className="form-bottom"><p><Icon name="shield" size={15} /> {mode === 'demo' ? 'Демо работает без ключей и интернета' : 'Запрос уйдёт в ваш FastAPI endpoint'}</p><button className="analyze-button" type="submit" disabled={status === 'loading'}>{status === 'loading' ? <><span className="button-spinner" /> Проверяем доказательства</> : <>Проверить ответ <Icon name="arrow" size={18} /></>}</button></div></form>
        <div className="example-row"><span>Попробовать пример:</span><button onClick={() => useExample(STARTER_TEXT)}><b className="example-dot red" /> Ошибка в факте</button><button onClick={() => useExample('Первый человек высадился на Марсе в 1969 году.')}><b className="example-dot amber" /> Галлюцинация</button><button onClick={() => useExample('Python был создан Гвидо ван Россумом в 1991 году.')}><b className="example-dot green" /> Верный ответ</button></div>
      </section>
      <section className="principles" id="how"><div className="principles-top"><p className="eyebrow">Прозрачный процесс</p><h2>Не «магический детектор лжи».<br /><em>Понятный путь к вердикту.</em></h2><p>Модель не становится источником истины. Она анализирует внешние доказательства — а вы видите всю логику проверки.</p></div><div className="principle-grid"><article><span className="principle-icon"><Icon name="layers" size={23} /></span><strong>1. Atomic claims</strong><p>Разделяем длинный ответ на независимые факты, которые можно проверить по отдельности.</p></article><article><span className="principle-icon"><Icon name="search" size={23} /></span><strong>2. External evidence</strong><p>Ищем подтверждения в независимых источниках, а не просим AI оценить самого себя.</p></article><article><span className="principle-icon"><Icon name="shield" size={23} /></span><strong>3. Explainable verdict</strong><p>Показываем статус, аргументацию и источник каждого важного вывода.</p></article></div></section>
      <div id="result-area" className="result-area">{status === 'loading' && <AnalysisLoader currentStep={step} />}{status === 'result' && result && <><AnalysisSummary result={result} onNewAnalysis={reset} /><ClaimResults result={result} /><section className="result-cta result-section"><div><p className="eyebrow">Ваше решение — ваше</p><h2>Senim AI показывает путь к фактам.</h2><p>Открывайте источники, оценивайте контекст и принимайте решение осознанно.</p></div><button className="outline-button" onClick={reset}>Проверить другой ответ <Icon name="arrow" size={18} /></button></section></>}</div>
    </main>
    <footer><Brand /><p>Проверка ответов AI на основе доказательств.</p><span>Built for WIT Teens Challenge Hackathon</span></footer>
    {scoreText && <div className="mobile-result-chip" role="status"><span className="live-dot" /> Анализ готов: {scoreText}</div>}
  </div>;
}

export default App;
