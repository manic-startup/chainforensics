<script>
	let txid = '';
	let loading = false;
	let error = null;
	let result = null;
	
	const API_BASE = 'http://localhost:3000/api/v1';
	
	async function analyzeTransaction() {
		if (!txid.trim()) {
			error = 'Please enter a transaction ID';
			return;
		}
		
		loading = true;
		error = null;
		result = null;
		
		try {
			const res = await fetch(`${API_BASE}/analysis/coinjoin/${txid}`);
			if (!res.ok) {
				const err = await res.json();
				throw new Error(err.detail || 'Analysis failed');
			}
			
			result = await res.json();
		} catch (e) {
			error = e.message;
		} finally {
			loading = false;
		}
	}
	
	function getScoreColor(score) {
		if (score >= 0.8) return '#f85149';
		if (score >= 0.5) return '#d29922';
		if (score >= 0.3) return '#8b949e';
		return '#238636';
	}
	
	function getProtocolInfo(protocol) {
		const protocols = {
			'whirlpool': { name: 'Whirlpool (Samourai)', icon: '🌀', desc: '5 equal outputs, specific denominations' },
			'wasabi': { name: 'Wasabi Wallet', icon: '🟢', desc: '10+ equal outputs with change' },
			'joinmarket': { name: 'JoinMarket', icon: '🔗', desc: 'Variable maker/taker structure' },
			'payjoin': { name: 'PayJoin (P2EP)', icon: '💳', desc: '2-party, disguised as normal payment' },
			'unknown_coinjoin': { name: 'Unknown CoinJoin', icon: '❓', desc: 'Equal output pattern detected' },
			'none': { name: 'Not CoinJoin', icon: '✅', desc: 'No mixing patterns detected' }
		};
		return protocols[protocol] || protocols['none'];
	}
</script>

<div class="coinjoin-page">
	<header>
		<h1>🔀 CoinJoin Detector</h1>
		<p>Analyze transactions for mixing patterns</p>
	</header>
	
	<section class="search-panel">
		<div class="input-group">
			<label for="txid">Transaction ID</label>
			<input 
				id="txid"
				type="text" 
				bind:value={txid}
				placeholder="Enter transaction ID to analyze"
				on:keypress={(e) => e.key === 'Enter' && analyzeTransaction()}
			/>
		</div>
		<button class="analyze-btn" on:click={analyzeTransaction} disabled={loading}>
			{loading ? '⏳ Analyzing...' : '🔍 Analyze'}
		</button>
	</section>
	
	{#if error}
		<div class="error-panel">❌ {error}</div>
	{/if}
	
	{#if result}
		<section class="results">
			<div class="score-card" style="--score-color: {getScoreColor(result.score)}">
				<div class="score-circle">
					<svg viewBox="0 0 100 100">
						<circle cx="50" cy="50" r="45" class="score-bg" />
						<circle 
							cx="50" cy="50" r="45" 
							class="score-fill"
							style="stroke-dasharray: {result.score * 283}, 283"
						/>
					</svg>
					<span class="score-value">{Math.round(result.score * 100)}%</span>
				</div>
				<div class="score-info">
					<h2>CoinJoin Score</h2>
					<p class="confidence">Confidence: {Math.round(result.confidence * 100)}%</p>
					{#if result.is_coinjoin}
						<span class="badge coinjoin">🔀 CoinJoin Detected</span>
					{:else}
						<span class="badge normal">✅ Normal Transaction</span>
					{/if}
				</div>
			</div>
			
			<div class="protocol-card">
				{@const proto = getProtocolInfo(result.protocol)}
				<div class="protocol-icon">{proto.icon}</div>
				<div class="protocol-info">
					<h3>{proto.name}</h3>
					<p>{proto.desc}</p>
				</div>
			</div>
			
			<div class="details-grid">
				<div class="detail-card">
					<h3>📊 Transaction Stats</h3>
					<dl>
						<dt>Inputs</dt>
						<dd>{result.transaction_stats?.input_count || 'N/A'}</dd>
						<dt>Outputs</dt>
						<dd>{result.transaction_stats?.output_count || 'N/A'}</dd>
						<dt>Total Output</dt>
						<dd>{result.transaction_stats?.total_output_btc?.toFixed(8) || 'N/A'} BTC</dd>
					</dl>
				</div>
				
				<div class="detail-card">
					<h3>✅ Matched Heuristics</h3>
					{#if result.heuristics_matched?.length > 0}
						<ul class="heuristics matched">
							{#each result.heuristics_matched as h}
								<li>✓ {h.replace(/_/g, ' ')}</li>
							{/each}
						</ul>
					{:else}
						<p class="no-data">No heuristics matched</p>
					{/if}
				</div>
				
				<div class="detail-card">
					<h3>❌ Failed Heuristics</h3>
					{#if result.heuristics_failed?.length > 0}
						<ul class="heuristics failed">
							{#each result.heuristics_failed as h}
								<li>✗ {h.replace(/_/g, ' ')}</li>
							{/each}
						</ul>
					{:else}
						<p class="no-data">No heuristics failed</p>
					{/if}
				</div>
			</div>
			
			{#if result.details}
				<div class="raw-details">
					<h3>📋 Analysis Details</h3>
					<pre>{JSON.stringify(result.details, null, 2)}</pre>
				</div>
			{/if}
		</section>
	{/if}
	
	<section class="info-panel">
		<h2>ℹ️ Supported CoinJoin Protocols</h2>
		<div class="protocol-list">
			<div class="protocol-item">
				<span class="proto-icon">🌀</span>
				<div>
					<strong>Whirlpool (Samourai)</strong>
					<p>Exactly 5 equal outputs with specific denominations (0.001, 0.01, 0.05, 0.5 BTC). Very high detection confidence.</p>
				</div>
			</div>
			<div class="protocol-item">
				<span class="proto-icon">🟢</span>
				<div>
					<strong>Wasabi Wallet</strong>
					<p>10+ equal outputs with change outputs present. High detection confidence.</p>
				</div>
			</div>
			<div class="protocol-item">
				<span class="proto-icon">🔗</span>
				<div>
					<strong>JoinMarket</strong>
					<p>Variable maker/taker structure with some equal outputs. Moderate detection confidence.</p>
				</div>
			</div>
			<div class="protocol-item">
				<span class="proto-icon">💳</span>
				<div>
					<strong>PayJoin (P2EP)</strong>
					<p>2-party mixing disguised as normal payment. Low detection confidence (designed to be undetectable).</p>
				</div>
			</div>
		</div>
	</section>
</div>

<style>
	.coinjoin-page {
		max-width: 1000px;
		margin: 0 auto;
	}
	
	header {
		margin-bottom: 24px;
	}
	
	header h1 {
		font-size: 24px;
		margin-bottom: 8px;
	}
	
	header p {
		color: #8b949e;
	}
	
	.search-panel {
		background: #161b22;
		border: 1px solid #30363d;
		border-radius: 8px;
		padding: 20px;
		margin-bottom: 24px;
		display: flex;
		gap: 16px;
		align-items: flex-end;
	}
	
	.input-group {
		flex: 1;
	}
	
	label {
		display: block;
		font-size: 14px;
		color: #8b949e;
		margin-bottom: 6px;
	}
	
	input {
		width: 100%;
		padding: 12px;
		background: #0d1117;
		border: 1px solid #30363d;
		border-radius: 6px;
		color: #c9d1d9;
		font-family: monospace;
		font-size: 14px;
	}
	
	input:focus {
		outline: none;
		border-color: #58a6ff;
	}
	
	.analyze-btn {
		padding: 12px 24px;
		background: #238636;
		border: none;
		border-radius: 6px;
		color: white;
		font-weight: 500;
		cursor: pointer;
		white-space: nowrap;
	}
	
	.analyze-btn:hover:not(:disabled) {
		background: #2ea043;
	}
	
	.analyze-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	
	.error-panel {
		background: #3d1f1f;
		border: 1px solid #f85149;
		border-radius: 8px;
		padding: 16px;
		margin-bottom: 24px;
		color: #f85149;
	}
	
	.results {
		margin-bottom: 24px;
	}
	
	.score-card {
		background: #161b22;
		border: 1px solid #30363d;
		border-radius: 8px;
		padding: 24px;
		display: flex;
		align-items: center;
		gap: 24px;
		margin-bottom: 16px;
	}
	
	.score-circle {
		position: relative;
		width: 120px;
		height: 120px;
	}
	
	.score-circle svg {
		transform: rotate(-90deg);
	}
	
	.score-bg {
		fill: none;
		stroke: #21262d;
		stroke-width: 8;
	}
	
	.score-fill {
		fill: none;
		stroke: var(--score-color);
		stroke-width: 8;
		stroke-linecap: round;
		transition: stroke-dasharray 0.5s ease;
	}
	
	.score-value {
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		font-size: 28px;
		font-weight: 600;
		color: var(--score-color);
	}
	
	.score-info h2 {
		margin: 0 0 8px;
		font-size: 20px;
	}
	
	.confidence {
		color: #8b949e;
		margin-bottom: 12px;
	}
	
	.badge {
		display: inline-block;
		padding: 6px 12px;
		border-radius: 16px;
		font-size: 14px;
		font-weight: 500;
	}
	
	.badge.coinjoin {
		background: rgba(248, 81, 73, 0.2);
		color: #f85149;
	}
	
	.badge.normal {
		background: rgba(35, 134, 54, 0.2);
		color: #238636;
	}
	
	.protocol-card {
		background: #161b22;
		border: 1px solid #30363d;
		border-radius: 8px;
		padding: 20px;
		display: flex;
		align-items: center;
		gap: 16px;
		margin-bottom: 16px;
	}
	
	.protocol-icon {
		font-size: 40px;
	}
	
	.protocol-info h3 {
		margin: 0 0 4px;
		font-size: 18px;
	}
	
	.protocol-info p {
		margin: 0;
		color: #8b949e;
	}
	
	.details-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
		gap: 16px;
		margin-bottom: 16px;
	}
	
	.detail-card {
		background: #161b22;
		border: 1px solid #30363d;
		border-radius: 8px;
		padding: 16px;
	}
	
	.detail-card h3 {
		font-size: 14px;
		margin: 0 0 12px;
		color: #8b949e;
	}
	
	dl {
		margin: 0;
	}
	
	dt {
		color: #8b949e;
		font-size: 12px;
		margin-top: 8px;
	}
	
	dt:first-child {
		margin-top: 0;
	}
	
	dd {
		margin: 2px 0 0;
		font-size: 16px;
		font-weight: 500;
	}
	
	.heuristics {
		list-style: none;
		padding: 0;
		margin: 0;
		font-size: 13px;
	}
	
	.heuristics li {
		padding: 4px 0;
	}
	
	.heuristics.matched li {
		color: #238636;
	}
	
	.heuristics.failed li {
		color: #8b949e;
	}
	
	.no-data {
		color: #6e7681;
		font-size: 13px;
		font-style: italic;
	}
	
	.raw-details {
		background: #161b22;
		border: 1px solid #30363d;
		border-radius: 8px;
		overflow: hidden;
	}
	
	.raw-details h3 {
		font-size: 14px;
		padding: 12px 16px;
		margin: 0;
		border-bottom: 1px solid #30363d;
		background: #0d1117;
		color: #8b949e;
	}
	
	.raw-details pre {
		margin: 0;
		padding: 16px;
		font-size: 12px;
		overflow-x: auto;
		color: #7ee787;
	}
	
	.info-panel {
		background: #161b22;
		border: 1px solid #30363d;
		border-radius: 8px;
		padding: 20px;
	}
	
	.info-panel h2 {
		font-size: 16px;
		margin-bottom: 16px;
	}
	
	.protocol-list {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}
	
	.protocol-item {
		display: flex;
		gap: 16px;
		padding: 12px;
		background: #0d1117;
		border-radius: 6px;
	}
	
	.proto-icon {
		font-size: 24px;
	}
	
	.protocol-item strong {
		display: block;
		margin-bottom: 4px;
	}
	
	.protocol-item p {
		margin: 0;
		font-size: 13px;
		color: #8b949e;
	}
</style>
