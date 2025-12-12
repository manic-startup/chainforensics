<script>
	import { onMount } from 'svelte';
	
	let txid = '';
	let direction = 'forward';
	let maxDepth = 10;
	let loading = false;
	let error = null;
	let timelineData = null;
	let asciiTimeline = '';
	
	const API_BASE = 'http://localhost:3000/api/v1';
	
	async function generateTimeline() {
		if (!txid.trim()) {
			error = 'Please enter a transaction ID';
			return;
		}
		
		loading = true;
		error = null;
		timelineData = null;
		asciiTimeline = '';
		
		try {
			// Get JSON timeline data
			const res = await fetch(
				`${API_BASE}/visualizations/timeline/json?txid=${txid}&direction=${direction}&max_depth=${maxDepth}`
			);
			
			if (!res.ok) {
				const err = await res.json();
				throw new Error(err.detail || 'Failed to generate timeline');
			}
			
			timelineData = await res.json();
			asciiTimeline = generateAsciiTimeline(timelineData);
			
		} catch (e) {
			error = e.message;
		} finally {
			loading = false;
		}
	}
	
	function generateAsciiTimeline(data) {
		const events = data.events || [];
		if (!events.length) return 'No timeline events to display.';
		
		// Find max value for scaling
		const maxValue = Math.max(...events.map(e => e.value_btc || 0)) || 1;
		const barWidth = 30;
		
		let lines = [];
		lines.push('═'.repeat(90));
		lines.push(' UTXO TIMELINE');
		lines.push(` Start: ${data.start_txid?.substring(0, 24)}...`);
		lines.push('═'.repeat(90));
		lines.push('');
		
		let currentDate = null;
		
		for (const event of events) {
			// Parse date
			const timestamp = event.timestamp;
			const dateStr = timestamp ? timestamp.substring(0, 10) : 'Unknown';
			
			// Date column
			const dateDisplay = dateStr !== currentDate ? dateStr : ' '.repeat(10);
			if (dateStr !== currentDate) currentDate = dateStr;
			
			// Value bar
			const value = event.value_btc || 0;
			const barLength = Math.max(1, Math.floor((value / maxValue) * barWidth));
			const bar = '█'.repeat(barLength);
			
			// Value string
			let valStr;
			if (value >= 0.1) {
				valStr = `${value.toFixed(4)} BTC`;
			} else if (value >= 0.001) {
				valStr = `${value.toFixed(6)} BTC`;
			} else {
				valStr = `${Math.floor(value * 100000000)} sats`;
			}
			
			// Status indicator
			const cjScore = event.coinjoin_score || 0;
			let indicator;
			if (cjScore > 0.7) {
				indicator = `🔀 CoinJoin (${Math.floor(cjScore * 100)}%)`;
			} else if (event.event_type === 'receive') {
				indicator = '💰 Received';
			} else if (event.event_type === 'mining') {
				indicator = '⛏️ Coinbase';
			} else {
				indicator = '📤 Transfer';
			}
			
			lines.push(`${dateDisplay} │ ${bar.padEnd(barWidth)} ${valStr.padEnd(15)} ${indicator}`);
		}
		
		lines.push(' '.repeat(10) + ' │');
		lines.push('═'.repeat(90));
		lines.push(` Total Events: ${data.event_count || events.length}`);
		lines.push(` CoinJoin Events: ${data.coinjoin_events || 0}`);
		if (data.date_range?.start && data.date_range?.end) {
			lines.push(` Date Range: ${data.date_range.start.substring(0, 10)} to ${data.date_range.end.substring(0, 10)}`);
		}
		lines.push('═'.repeat(90));
		
		return lines.join('\n');
	}
	
	function copyToClipboard() {
		navigator.clipboard.writeText(asciiTimeline);
	}
</script>

<div class="timeline-page">
	<header>
		<h1>📅 UTXO Timeline</h1>
		<p>Visualize the flow of funds through transactions over time</p>
	</header>
	
	<section class="search-panel">
		<div class="input-group">
			<label for="txid">Transaction ID</label>
			<input 
				id="txid"
				type="text" 
				bind:value={txid}
				placeholder="Enter transaction ID (64 hex characters)"
				class="txid-input"
			/>
		</div>
		
		<div class="options">
			<div class="input-group">
				<label for="direction">Direction</label>
				<select id="direction" bind:value={direction}>
					<option value="forward">Forward (where funds went)</option>
					<option value="backward">Backward (where funds came from)</option>
				</select>
			</div>
			
			<div class="input-group">
				<label for="depth">Max Depth</label>
				<input 
					id="depth"
					type="number" 
					bind:value={maxDepth}
					min="1"
					max="30"
				/>
			</div>
			
			<button class="generate-btn" on:click={generateTimeline} disabled={loading}>
				{loading ? '⏳ Generating...' : '📊 Generate Timeline'}
			</button>
		</div>
	</section>
	
	{#if error}
		<div class="error-panel">
			<span class="error-icon">❌</span>
			<span>{error}</span>
		</div>
	{/if}
	
	{#if asciiTimeline}
		<section class="timeline-output">
			<div class="output-header">
				<h2>Timeline View</h2>
				<button class="copy-btn" on:click={copyToClipboard}>📋 Copy</button>
			</div>
			<pre class="ascii-timeline">{asciiTimeline}</pre>
		</section>
	{/if}
	
	{#if timelineData}
		<section class="visual-timeline">
			<h2>Visual Timeline</h2>
			<div class="events-container">
				{#each timelineData.events || [] as event, i}
					<div class="event-row" class:coinjoin={event.coinjoin_score > 0.5}>
						<div class="event-date">
							{event.timestamp ? event.timestamp.substring(0, 10) : 'Unknown'}
						</div>
						<div class="event-bar-container">
							<div 
								class="event-bar"
								style="width: {Math.max(5, (event.value_btc / (timelineData.total_value_btc || 1)) * 100)}%"
							></div>
						</div>
						<div class="event-value">
							{event.value_btc?.toFixed(8)} BTC
						</div>
						<div class="event-type">
							{#if event.coinjoin_score > 0.5}
								🔀 CoinJoin
							{:else if event.event_type === 'mining'}
								⛏️ Coinbase
							{:else if event.event_type === 'receive'}
								💰 Received
							{:else}
								📤 Transfer
							{/if}
						</div>
						<div class="event-txid">
							{event.txid?.substring(0, 16)}...
						</div>
					</div>
				{/each}
			</div>
		</section>
		
		<section class="summary-panel">
			<h2>Summary</h2>
			<div class="summary-grid">
				<div class="summary-item">
					<span class="summary-value">{timelineData.event_count || 0}</span>
					<span class="summary-label">Total Events</span>
				</div>
				<div class="summary-item">
					<span class="summary-value">{timelineData.coinjoin_events || 0}</span>
					<span class="summary-label">CoinJoin Events</span>
				</div>
				<div class="summary-item">
					<span class="summary-value">{(timelineData.total_value_btc || 0).toFixed(4)}</span>
					<span class="summary-label">Total BTC</span>
				</div>
			</div>
		</section>
	{/if}
	
	<section class="help-panel">
		<h2>ℹ️ How to Use</h2>
		<ol>
			<li>Enter a Bitcoin transaction ID (txid)</li>
			<li>Choose direction: <strong>Forward</strong> to see where funds went, <strong>Backward</strong> to see where they came from</li>
			<li>Set the max depth to control how far to trace</li>
			<li>Click Generate to create the timeline</li>
		</ol>
		<p class="tip">
			💡 <strong>Tip:</strong> CoinJoin transactions are highlighted in red. 
			These indicate privacy-enhancing mixing that can break transaction tracing.
		</p>
	</section>
</div>

<style>
	.timeline-page {
		max-width: 1200px;
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
	
	h2 {
		font-size: 16px;
		margin-bottom: 16px;
		color: #c9d1d9;
	}
	
	.search-panel {
		background: #161b22;
		border: 1px solid #30363d;
		border-radius: 8px;
		padding: 20px;
		margin-bottom: 24px;
	}
	
	.input-group {
		margin-bottom: 16px;
	}
	
	.input-group label {
		display: block;
		font-size: 14px;
		color: #8b949e;
		margin-bottom: 6px;
	}
	
	.txid-input {
		width: 100%;
		padding: 12px;
		background: #0d1117;
		border: 1px solid #30363d;
		border-radius: 6px;
		color: #c9d1d9;
		font-family: monospace;
		font-size: 14px;
	}
	
	.txid-input:focus {
		outline: none;
		border-color: #58a6ff;
	}
	
	.options {
		display: flex;
		gap: 16px;
		align-items: flex-end;
		flex-wrap: wrap;
	}
	
	.options .input-group {
		margin-bottom: 0;
	}
	
	select, input[type="number"] {
		padding: 10px 12px;
		background: #0d1117;
		border: 1px solid #30363d;
		border-radius: 6px;
		color: #c9d1d9;
		font-size: 14px;
	}
	
	select:focus, input[type="number"]:focus {
		outline: none;
		border-color: #58a6ff;
	}
	
	.generate-btn {
		padding: 10px 20px;
		background: #238636;
		border: none;
		border-radius: 6px;
		color: white;
		font-size: 14px;
		font-weight: 500;
		cursor: pointer;
		transition: background 0.2s;
	}
	
	.generate-btn:hover:not(:disabled) {
		background: #2ea043;
	}
	
	.generate-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	
	.error-panel {
		background: #3d1f1f;
		border: 1px solid #f85149;
		border-radius: 8px;
		padding: 16px;
		margin-bottom: 24px;
		display: flex;
		align-items: center;
		gap: 12px;
		color: #f85149;
	}
	
	.timeline-output {
		background: #161b22;
		border: 1px solid #30363d;
		border-radius: 8px;
		margin-bottom: 24px;
		overflow: hidden;
	}
	
	.output-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 16px 20px;
		border-bottom: 1px solid #30363d;
	}
	
	.output-header h2 {
		margin: 0;
	}
	
	.copy-btn {
		padding: 6px 12px;
		background: #21262d;
		border: 1px solid #30363d;
		border-radius: 6px;
		color: #8b949e;
		font-size: 13px;
		cursor: pointer;
	}
	
	.copy-btn:hover {
		background: #30363d;
		color: #c9d1d9;
	}
	
	.ascii-timeline {
		padding: 20px;
		margin: 0;
		font-family: 'Consolas', 'Monaco', monospace;
		font-size: 13px;
		line-height: 1.5;
		overflow-x: auto;
		background: #0d1117;
		color: #7ee787;
	}
	
	.visual-timeline {
		background: #161b22;
		border: 1px solid #30363d;
		border-radius: 8px;
		padding: 20px;
		margin-bottom: 24px;
	}
	
	.events-container {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	
	.event-row {
		display: grid;
		grid-template-columns: 100px 1fr 120px 100px 150px;
		gap: 12px;
		align-items: center;
		padding: 12px;
		background: #0d1117;
		border-radius: 6px;
		font-size: 13px;
	}
	
	.event-row.coinjoin {
		border-left: 3px solid #f85149;
	}
	
	.event-date {
		color: #8b949e;
		font-family: monospace;
	}
	
	.event-bar-container {
		height: 20px;
		background: #21262d;
		border-radius: 4px;
		overflow: hidden;
	}
	
	.event-bar {
		height: 100%;
		background: linear-gradient(90deg, #238636, #2ea043);
		border-radius: 4px;
		transition: width 0.3s ease;
	}
	
	.event-row.coinjoin .event-bar {
		background: linear-gradient(90deg, #f85149, #da3633);
	}
	
	.event-value {
		font-family: monospace;
		color: #58a6ff;
		text-align: right;
	}
	
	.event-type {
		color: #8b949e;
	}
	
	.event-txid {
		font-family: monospace;
		color: #6e7681;
		font-size: 11px;
	}
	
	.summary-panel {
		background: #161b22;
		border: 1px solid #30363d;
		border-radius: 8px;
		padding: 20px;
		margin-bottom: 24px;
	}
	
	.summary-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 20px;
	}
	
	.summary-item {
		text-align: center;
	}
	
	.summary-value {
		display: block;
		font-size: 28px;
		font-weight: 600;
		color: #58a6ff;
		margin-bottom: 4px;
	}
	
	.summary-label {
		font-size: 13px;
		color: #8b949e;
	}
	
	.help-panel {
		background: #161b22;
		border: 1px solid #30363d;
		border-radius: 8px;
		padding: 20px;
	}
	
	.help-panel ol {
		margin: 0 0 16px 20px;
		color: #8b949e;
		line-height: 1.8;
	}
	
	.tip {
		background: #0d1117;
		padding: 12px;
		border-radius: 6px;
		font-size: 13px;
		color: #8b949e;
	}
</style>
