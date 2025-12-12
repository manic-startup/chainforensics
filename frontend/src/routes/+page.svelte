<script>
	import { onMount } from 'svelte';
	
	let health = null;
	let loading = true;
	let error = null;
	
	const API_BASE = 'http://localhost:3000';
	
	onMount(async () => {
		try {
			const res = await fetch(`${API_BASE}/health`);
			health = await res.json();
		} catch (e) {
			error = 'Cannot connect to ChainForensics API';
		} finally {
			loading = false;
		}
	});
</script>

<div class="dashboard">
	<header>
		<h1>🔗 ChainForensics Dashboard</h1>
		<p class="subtitle">Privacy-focused Bitcoin UTXO Analysis</p>
	</header>
	
	<section class="status-cards">
		<div class="card">
			<div class="card-icon">🖥️</div>
			<div class="card-content">
				<h3>API Status</h3>
				{#if loading}
					<p class="status loading">Checking...</p>
				{:else if error}
					<p class="status error">❌ Disconnected</p>
				{:else}
					<p class="status success">✅ Operational</p>
				{/if}
			</div>
		</div>
		
		<div class="card">
			<div class="card-icon">₿</div>
			<div class="card-content">
				<h3>Bitcoin Core</h3>
				{#if loading}
					<p class="status loading">Checking...</p>
				{:else if health?.components?.bitcoin_core?.status === 'connected'}
					<p class="status success">✅ Block {health.components.bitcoin_core.blocks?.toLocaleString()}</p>
				{:else}
					<p class="status error">❌ Not connected</p>
				{/if}
			</div>
		</div>
		
		<div class="card">
			<div class="card-icon">💾</div>
			<div class="card-content">
				<h3>Database</h3>
				{#if loading}
					<p class="status loading">Checking...</p>
				{:else if health?.components?.database?.status === 'connected'}
					<p class="status success">✅ Connected</p>
				{:else}
					<p class="status error">❌ Not connected</p>
				{/if}
			</div>
		</div>
	</section>
	
	<section class="quick-actions">
		<h2>Quick Actions</h2>
		<div class="action-grid">
			<a href="/trace" class="action-card">
				<span class="action-icon">🔍</span>
				<div>
					<h3>Trace Transaction</h3>
					<p>Follow funds through the blockchain</p>
				</div>
			</a>
			
			<a href="/coinjoin" class="action-card">
				<span class="action-icon">🔀</span>
				<div>
					<h3>Detect CoinJoin</h3>
					<p>Analyze mixing transactions</p>
				</div>
			</a>
			
			<a href="/timeline" class="action-card">
				<span class="action-icon">📅</span>
				<div>
					<h3>View Timeline</h3>
					<p>Visualize transaction history</p>
				</div>
			</a>
			
			<a href="/addresses" class="action-card">
				<span class="action-icon">📝</span>
				<div>
					<h3>Manage Labels</h3>
					<p>Label known addresses</p>
				</div>
			</a>
		</div>
	</section>
	
	<section class="info-panel">
		<h2>ℹ️ About ChainForensics</h2>
		<p>
			ChainForensics is a privacy-focused blockchain analysis tool that runs entirely 
			on your local network. All queries go through your own Bitcoin Core node - 
			no external APIs or block explorers are used.
		</p>
		<div class="features">
			<div class="feature">
				<strong>🔒 100% Local</strong>
				<span>All data stays on your LAN</span>
			</div>
			<div class="feature">
				<strong>🔀 CoinJoin Detection</strong>
				<span>Whirlpool, Wasabi, JoinMarket</span>
			</div>
			<div class="feature">
				<strong>📊 Visual Analysis</strong>
				<span>Timelines and flow diagrams</span>
			</div>
			<div class="feature">
				<strong>🤖 MCP Integration</strong>
				<span>Use with Claude Desktop</span>
			</div>
		</div>
	</section>
</div>

<style>
	.dashboard {
		max-width: 1200px;
		margin: 0 auto;
	}
	
	header {
		margin-bottom: 32px;
	}
	
	h1 {
		font-size: 28px;
		color: #c9d1d9;
		margin-bottom: 8px;
	}
	
	.subtitle {
		color: #8b949e;
		font-size: 16px;
	}
	
	h2 {
		font-size: 18px;
		color: #c9d1d9;
		margin-bottom: 16px;
	}
	
	.status-cards {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 16px;
		margin-bottom: 32px;
	}
	
	.card {
		background: #161b22;
		border: 1px solid #30363d;
		border-radius: 8px;
		padding: 20px;
		display: flex;
		align-items: center;
		gap: 16px;
	}
	
	.card-icon {
		font-size: 32px;
	}
	
	.card-content h3 {
		font-size: 14px;
		color: #8b949e;
		font-weight: 500;
		margin-bottom: 4px;
	}
	
	.status {
		font-size: 14px;
		font-weight: 500;
	}
	
	.status.success { color: #238636; }
	.status.error { color: #f85149; }
	.status.loading { color: #8b949e; }
	
	.quick-actions {
		margin-bottom: 32px;
	}
	
	.action-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
		gap: 16px;
	}
	
	.action-card {
		background: #161b22;
		border: 1px solid #30363d;
		border-radius: 8px;
		padding: 20px;
		display: flex;
		align-items: center;
		gap: 16px;
		text-decoration: none;
		color: inherit;
		transition: all 0.2s;
	}
	
	.action-card:hover {
		border-color: #58a6ff;
		transform: translateY(-2px);
	}
	
	.action-icon {
		font-size: 28px;
	}
	
	.action-card h3 {
		font-size: 16px;
		color: #c9d1d9;
		margin-bottom: 4px;
	}
	
	.action-card p {
		font-size: 13px;
		color: #8b949e;
	}
	
	.info-panel {
		background: #161b22;
		border: 1px solid #30363d;
		border-radius: 8px;
		padding: 24px;
	}
	
	.info-panel > p {
		color: #8b949e;
		line-height: 1.6;
		margin-bottom: 20px;
	}
	
	.features {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 16px;
	}
	
	.feature {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	
	.feature strong {
		color: #c9d1d9;
	}
	
	.feature span {
		font-size: 13px;
		color: #8b949e;
	}
</style>
