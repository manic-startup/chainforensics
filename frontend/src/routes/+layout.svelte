<script>
	import { page } from '$app/stores';
</script>

<div class="app">
	<nav class="sidebar">
		<div class="logo">
			<span class="logo-icon">🔗</span>
			<span class="logo-text">ChainForensics</span>
		</div>
		
		<ul class="nav-links">
			<li class:active={$page.url.pathname === '/'}>
				<a href="/">
					<span class="icon">📊</span>
					Dashboard
				</a>
			</li>
			<li class:active={$page.url.pathname === '/trace'}>
				<a href="/trace">
					<span class="icon">🔍</span>
					Trace UTXO
				</a>
			</li>
			<li class:active={$page.url.pathname === '/timeline'}>
				<a href="/timeline">
					<span class="icon">📅</span>
					Timeline
				</a>
			</li>
			<li class:active={$page.url.pathname === '/coinjoin'}>
				<a href="/coinjoin">
					<span class="icon">🔀</span>
					CoinJoin Detector
				</a>
			</li>
			<li class:active={$page.url.pathname === '/addresses'}>
				<a href="/addresses">
					<span class="icon">📝</span>
					Address Labels
				</a>
			</li>
			<li class:active={$page.url.pathname === '/jobs'}>
				<a href="/jobs">
					<span class="icon">⚙️</span>
					Jobs
				</a>
			</li>
		</ul>
		
		<div class="status-indicator">
			<div class="status-dot"></div>
			<span>Connected</span>
		</div>
	</nav>
	
	<main class="content">
		<slot />
	</main>
</div>

<style>
	:global(*) {
		margin: 0;
		padding: 0;
		box-sizing: border-box;
	}
	
	:global(body) {
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
		background: #0d1117;
		color: #c9d1d9;
		min-height: 100vh;
	}
	
	.app {
		display: flex;
		min-height: 100vh;
	}
	
	.sidebar {
		width: 240px;
		background: #161b22;
		border-right: 1px solid #30363d;
		padding: 20px 0;
		display: flex;
		flex-direction: column;
		position: fixed;
		height: 100vh;
	}
	
	.logo {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 0 20px 20px;
		border-bottom: 1px solid #30363d;
		margin-bottom: 20px;
	}
	
	.logo-icon {
		font-size: 24px;
	}
	
	.logo-text {
		font-size: 18px;
		font-weight: 600;
		color: #58a6ff;
	}
	
	.nav-links {
		list-style: none;
		flex: 1;
	}
	
	.nav-links li {
		margin: 4px 8px;
	}
	
	.nav-links a {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 12px 16px;
		color: #8b949e;
		text-decoration: none;
		border-radius: 6px;
		transition: all 0.2s;
	}
	
	.nav-links a:hover {
		background: #21262d;
		color: #c9d1d9;
	}
	
	.nav-links li.active a {
		background: #21262d;
		color: #58a6ff;
	}
	
	.icon {
		font-size: 18px;
	}
	
	.status-indicator {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 16px 20px;
		border-top: 1px solid #30363d;
		font-size: 12px;
		color: #8b949e;
	}
	
	.status-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: #238636;
	}
	
	.content {
		flex: 1;
		margin-left: 240px;
		padding: 24px;
		min-height: 100vh;
	}
</style>
