<script>
	let txid = '';
	let vout = 0;
	let direction = 'forward';
	let maxDepth = 10;
	let loading = false;
	let error = null;
	let traceResult = null;
	
	const API_BASE = 'http://localhost:3000/api/v1';
	
	async function runTrace() {
		if (!txid.trim()) {
			error = 'Please enter a transaction ID';
			return;
		}
		
		loading = true;
		error = null;
		traceResult = null;
		
		try {
			let url;
			if (direction === 'forward') {
				url = `${API_BASE}/analysis/trace/forward?txid=${txid}&vout=${vout}&max_depth=${maxDepth}`;
			} else {
				url = `${API_BASE}/analysis/trace/backward?txid=${txid}&max_depth=${maxDepth}`;
			}
			
			const res = await fetch(url);
			if (!res.ok) {
				const err = await res.json();
				throw new Error(err.detail || 'Trace failed');
			}
			
			traceResult = await res.json();
		} catch (e) {
			error = e.message;
		} finally {
			loading = false;
		}
	}
</script>

<div class="trace-page">
	<header>
		<h1>🔍 Trace UTXO</h1>
		<p>Follow the flow of funds through the blockchain</p>
	</header>
	
	<section class="search-panel">
		<div class="input-row">
			<div class="input-group flex-grow">
				<label for="txid">Transaction ID</label>
				<input 
					id="txid"
					type="text" 
					bind:value={txid}
					placeholder="Enter transaction ID"
					class="txid-input"
				/>
			</div>
			
			<div class="input-group">
				<label for="vout">Output Index</label>
				<input 
					id="vout"
					type="number" 
					bind:value={vout}
					min="0"
				/>
			</div>
		</div>
		
		<div class="options">
			<div class="input-group">
				<label for="direction">Direction</label>
				<select id="direction" bind:value={direction}>
					<option value="forward">Forward (spending)</option>
					<option value="backward">Backward (origins)</option>
				</select>
			</div>
			
			<div class="input-group">
				<label for="depth">Max Depth</label>
				<input 
					id="depth"
					type="number" 
					bind:value={maxDepth}
					min="1"
					max="50"
				/>
			</div>
			
			<button class="trace-btn" on:click={runTrace} disabled={loading}>
				{loading ? '⏳ Tracing...' : '🔍 Run Trace'}
			</button>
		</div>
	</section>
	
	{#if error}
		<div class="error-panel">
			<span>❌ {error}</span>
		</div>
	{/if}
	
	{#if traceResult}
		<section class="results">
			<div class="stats-row">
				<div class="stat-card">
					<span class="stat-value">{traceResult.total_transactions || 0}</span>
					<span class="stat-label">Transactions Analyzed</span>
				</div>
				<div class="stat-card">
					<span class="stat-value">{traceResult.summary?.unspent_count || 0}</span>
					<span class="stat-label">Unspent Outputs</span>
				</div>
				<div class="stat-card">
					<span class="stat-value">{traceResult.summary?.coinbase_count || 0}</span>
					<span class="stat-label">Coinbase Origins</span>
				</div>
				<div class="stat-card">
					<span class="stat-value">{traceResult.summary?.coinjoin_count || 0}</span>
					<span class="stat-label">CoinJoin Transactions</span>
				</div>
				<div class="stat-card">
					<span class="stat-value">{traceResult.execution_time_ms || 0}ms</span>
					<span class="stat-label">Execution Time</span>
				</div>
			</div>
			
			{#if traceResult.coinjoin_txids?.length > 0}
				<div class="coinjoin-warning">
					<h3>🔀 CoinJoin Detected</h3>
					<p>The following transactions appear to be CoinJoin mixing transactions:</p>
					<ul>
						{#each traceResult.coinjoin_txids as cjtxid}
							<li><code>{cjtxid}</code></li>
						{/each}
					</ul>
				</div>
			{/if}
			
			<h2>Trace Nodes ({traceResult.nodes?.length || 0})</h2>
			<div class="nodes-table">
				<table>
					<thead>
						<tr>
							<th>Depth</th>
							<th>TXID</th>
							<th>Vout</th>
							<th>Value</th>
							<th>Status</th>
							<th>Block</th>
							<th>CJ Score</th>
						</tr>
					</thead>
					<tbody>
						{#each traceResult.nodes || [] as node}
							<tr class:coinjoin={node.coinjoin_score > 0.5}>
								<td>{node.depth}</td>
								<td class="txid">{node.txid?.substring(0, 16)}...</td>
								<td>{node.vout}</td>
								<td class="value">{node.value_btc?.toFixed(8)} BTC</td>
								<td>
									{#if node.status === 'unspent'}
										<span class="status-unspent">💰 Unspent</span>
									{:else if node.status === 'coinbase'}
										<span class="status-coinbase">⛏️ Coinbase</span>
									{:else}
										<span class="status-spent">📤 Spent</span>
									{/if}
								</td>
								<td>{node.block_height || 'N/A'}</td>
								<td>
									{#if node.coinjoin_score > 0.7}
										<span class="cj-high">🔀 {(node.coinjoin_score * 100).toFixed(0)}%</span>
									{:else if node.coinjoin_score > 0.3}
										<span class="cj-med">{(node.coinjoin_score * 100).toFixed(0)}%</span>
									{:else}
										<span class="cj-low">{(node.coinjoin_score * 100).toFixed(0)}%</span>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			
			{#if traceResult.warnings?.length > 0}
				<div class="warnings">
					<h3>⚠️ Warnings</h3>
					<ul>
						{#each traceResult.warnings as warning}
							<li>{warning}</li>
						{/each}
					</ul>
				</div>
			{/if}
		</section>
	{/if}
</div>

<style>
	.trace-page {
		max-width: 1400px;
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
	}
	
	.input-row {
		display: flex;
		gap: 16px;
		margin-bottom: 16px;
	}
	
	.input-group {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	
	.flex-grow {
		flex: 1;
	}
	
	label {
		font-size: 14px;
		color: #8b949e;
	}
	
	input, select {
		padding: 10px 12px;
		background: #0d1117;
		border: 1px solid #30363d;
		border-radius: 6px;
		color: #c9d1d9;
		font-size: 14px;
	}
	
	.txid-input {
		font-family: monospace;
	}
	
	input:focus, select:focus {
		outline: none;
		border-color: #58a6ff;
	}
	
	.options {
		display: flex;
		gap: 16px;
		align-items: flex-end;
	}
	
	.trace-btn {
		padding: 10px 24px;
		background: #238636;
		border: none;
		border-radius: 6px;
		color: white;
		font-weight: 500;
		cursor: pointer;
	}
	
	.trace-btn:hover:not(:disabled) {
		background: #2ea043;
	}
	
	.trace-btn:disabled {
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
		background: #161b22;
		border: 1px solid #30363d;
		border-radius: 8px;
		padding: 20px;
	}
	
	.stats-row {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 16px;
		margin-bottom: 24px;
	}
	
	.stat-card {
		background: #0d1117;
		border-radius: 8px;
		padding: 16px;
		text-align: center;
	}
	
	.stat-value {
		display: block;
		font-size: 24px;
		font-weight: 600;
		color: #58a6ff;
		margin-bottom: 4px;
	}
	
	.stat-label {
		font-size: 12px;
		color: #8b949e;
	}
	
	.coinjoin-warning {
		background: #3d1f1f;
		border: 1px solid #f85149;
		border-radius: 8px;
		padding: 16px;
		margin-bottom: 24px;
	}
	
	.coinjoin-warning h3 {
		color: #f85149;
		margin-bottom: 8px;
	}
	
	.coinjoin-warning p {
		color: #f0a0a0;
		margin-bottom: 12px;
	}
	
	.coinjoin-warning ul {
		list-style: none;
		padding: 0;
	}
	
	.coinjoin-warning li {
		margin: 4px 0;
	}
	
	.coinjoin-warning code {
		font-family: monospace;
		font-size: 12px;
		color: #ffa0a0;
	}
	
	h2 {
		font-size: 16px;
		margin-bottom: 16px;
		color: #c9d1d9;
	}
	
	.nodes-table {
		overflow-x: auto;
	}
	
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 13px;
	}
	
	th, td {
		padding: 12px;
		text-align: left;
		border-bottom: 1px solid #21262d;
	}
	
	th {
		color: #8b949e;
		font-weight: 500;
		background: #0d1117;
	}
	
	tr.coinjoin {
		background: rgba(248, 81, 73, 0.1);
	}
	
	.txid {
		font-family: monospace;
		color: #58a6ff;
	}
	
	.value {
		font-family: monospace;
	}
	
	.status-unspent { color: #238636; }
	.status-coinbase { color: #a371f7; }
	.status-spent { color: #8b949e; }
	
	.cj-high { color: #f85149; font-weight: 600; }
	.cj-med { color: #d29922; }
	.cj-low { color: #8b949e; }
	
	.warnings {
		margin-top: 20px;
		padding: 16px;
		background: #2d2a1d;
		border: 1px solid #d29922;
		border-radius: 8px;
	}
	
	.warnings h3 {
		color: #d29922;
		margin-bottom: 12px;
	}
	
	.warnings ul {
		margin: 0;
		padding-left: 20px;
		color: #e0d090;
	}
</style>
