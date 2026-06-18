// ===== データ読み込み =====
async function loadJSON(path) {
  const res = await fetch(path);
  return res.json();
}

// ===== 色パレット（10チーム分） =====
const COLORS = [
  '#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6',
  '#1abc9c', '#e67e22', '#e91e8c', '#00bcd4', '#cddc39'
];

// ===== 選手の累積ポイント計算 =====
function buildPlayerStats(matches) {
  const stats = {};
  for (const match of matches) {
    for (const p of match.players) {
      if (!p.player) continue;
      if (!stats[p.player]) {
        stats[p.player] = {
          total: 0, bestScore: -Infinity, tops: 0,
          fourthCount: 0, games: 0, image: p.image || null,
          history: []
        };
      }
      const s = stats[p.player];
      s.total += p.score;
      s.games++;
      if (p.score > s.bestScore) s.bestScore = p.score;
      if (p.rank === 1) s.tops++;
      if (p.rank === 4) s.fourthCount++;
      s.history.push({ date: match.date, score: p.score, cumulative: s.total });
    }
  }
  return stats;
}

// ===== ドラフトチームのポイント計算 =====
function buildTeamStats(draftTeams, playerStats) {
  return draftTeams.map(team => {
    const players = team.players.map(name => ({
      name,
      total: playerStats[name]?.total ?? 0,
      image: playerStats[name]?.image ?? null,
      history: playerStats[name]?.history ?? []
    }));
    const total = players.reduce((sum, p) => sum + p.total, 0);

    const allDates = [...new Set(
      players.flatMap(p => p.history.map(h => h.date))
    )].sort();

    const cumulativeByDate = allDates.map(date => {
      const teamSum = players.reduce((sum, p) => {
        const h = p.history.findLast(h => h.date <= date);
        return sum + (h ? h.cumulative : 0);
      }, 0);
      return { date, value: teamSum };
    });

    return { ...team, players, total, cumulativeByDate };
  });
}

// ===== グラフ描画: 選手推移 =====
let playerChart = null;
function renderPlayerChart(team, playerStats) {
  const ctx = document.getElementById('player-chart').getContext('2d');

  const allDates = [...new Set(
    team.players.flatMap(name => (playerStats[name]?.history ?? []).map(h => h.date))
  )].sort();

  const datasets = team.players.map((name, i) => {
    const history = playerStats[name]?.history ?? [];
    const data = allDates.map(date => {
      const h = history.findLast(h => h.date <= date);
      return h ? h.cumulative : null;
    });
    return {
      label: name,
      data,
      borderColor: COLORS[i % COLORS.length],
      backgroundColor: COLORS[i % COLORS.length] + '33',
      tension: 0.3,
      pointRadius: 3,
      spanGaps: true
    };
  });

  if (playerChart) playerChart.destroy();
  playerChart = new Chart(ctx, {
    type: 'line',
    data: { labels: allDates, datasets },
    options: chartOptions('pt')
  });
}

// ===== グラフ描画: チーム推移 =====
let teamChart = null;
function renderTeamChart(teamStats) {
  const ctx = document.getElementById('team-chart').getContext('2d');

  const allDates = [...new Set(
    teamStats.flatMap(t => t.cumulativeByDate.map(d => d.date))
  )].sort();

  const datasets = teamStats.map((team, i) => ({
    label: team.name,
    data: allDates.map(date => {
      const d = team.cumulativeByDate.findLast(d => d.date <= date);
      return d ? d.value : null;
    }),
    borderColor: COLORS[i % COLORS.length],
    backgroundColor: COLORS[i % COLORS.length] + '33',
    tension: 0.3,
    pointRadius: 3,
    spanGaps: true
  }));

  if (teamChart) teamChart.destroy();
  teamChart = new Chart(ctx, {
    type: 'line',
    data: { labels: allDates, datasets },
    options: chartOptions('pt')
  });
}

function chartOptions(unit) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { labels: { color: '#e8f5ee', font: { size: 10 } } },
      tooltip: {
        callbacks: {
          label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(1)}${unit}`
        }
      }
    },
    scales: {
      x: {
        ticks: { color: '#7fad8f', maxTicksLimit: 8, font: { size: 9 } },
        grid: { color: '#1e3828' }
      },
      y: {
        ticks: { color: '#7fad8f', callback: v => `${v}pt`, font: { size: 9 } },
        grid: { color: '#1e3828' }
      }
    }
  };
}

// ===== チームランキング描画 =====
function renderTeamRanking(teamStats) {
  const sorted = [...teamStats].sort((a, b) => b.total - a.total);
  const el = document.getElementById('team-ranking');
  el.innerHTML = sorted.map((team, i) => {
    const rank = i + 1;
    const rankClass = rank <= 3 ? `rank-${rank}` : '';
    const scoreClass = team.total >= 0 ? '' : 'negative';

    const playersHtml = team.players.map(p => {
      const imgSrc = p.image ? p.image : 'images/placeholder.png';
      const scoreClass2 = p.total >= 0 ? 'positive' : 'negative';
      return `
        <div class="player-chip">
          <img src="${imgSrc}" alt="${p.name}" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22/>'">
          <span class="chip-name">${p.name}</span>
          <span class="chip-score ${scoreClass2}">${p.total >= 0 ? '+' : ''}${p.total.toFixed(1)}</span>
        </div>`;
    }).join('');

    return `
      <div class="team-rank-item ${rankClass}">
        <div class="rank-badge">${rank}</div>
        <div class="team-rank-info">
          <div class="team-rank-header">
            <div class="team-name-block">
              <span class="team-name">${team.name}</span>
              <span class="team-owner">${team.owner ?? ''}</span>
            </div>
            <span class="team-score ${scoreClass}">${team.total >= 0 ? '+' : ''}${team.total.toFixed(1)}pt</span>
          </div>
          <div class="players-row">${playersHtml}</div>
        </div>
      </div>`;
  }).join('');
}

// ===== アワード描画 =====
function renderAwards(playerStats, draftTeams) {
  const playerTeamMap = {};
  for (const team of draftTeams) {
    for (const name of team.players) {
      playerTeamMap[name] = { teamName: team.name, owner: team.owner ?? '' };
    }
  }

  const players = Object.entries(playerStats).map(([name, s]) => ({
    name,
    teamName: playerTeamMap[name]?.teamName ?? '—',
    owner: playerTeamMap[name]?.owner ?? '',
    total: s.total,
    bestScore: s.bestScore === -Infinity ? 0 : s.bestScore,
    avoidRate: s.games > 0 ? ((s.games - s.fourthCount) / s.games * 100) : 0,
    tops: s.tops
  }));

  renderAwardBlock('award-total', players, 'total', v => `${v >= 0 ? '+' : ''}${v.toFixed(1)}pt`);
  renderAwardBlock('award-best', players, 'bestScore', v => `${v.toFixed(1)}pt`);
  renderAwardBlock('award-avoid', players, 'avoidRate', v => `${v.toFixed(1)}%`);
  renderAwardBlock('award-top', players, 'tops', v => `${v}回`);
}

function renderAwardBlock(id, players, key, fmt) {
  const sorted = [...players].sort((a, b) => b[key] - a[key]).slice(0, 3);
  const el = document.getElementById(id);
  el.innerHTML = sorted.map((p, i) => {
    const medal = ['🥇', '🥈', '🥉'][i];
    return `
      <div class="award-row">
        <span class="award-rank">${medal}</span>
        <div class="award-info">
          <div class="award-player">${p.name}</div>
          <div class="award-team">${p.teamName}</div>
          <div class="award-owner">${p.owner}</div>
        </div>
        <span class="award-value">${fmt(p[key])}</span>
      </div>`;
  }).join('');
}

// ===== 役満描画 =====
function renderYakuman(yakumanData, draftTeams) {
  const playerTeamMap = {};
  for (const team of draftTeams) {
    for (const name of team.players) {
      playerTeamMap[name] = { teamName: team.name, owner: team.owner ?? '' };
    }
  }

  const el = document.getElementById('yakuman-list');
  const list = yakumanData.yakuman ?? [];
  if (list.length === 0) {
    el.innerHTML = '<p class="empty-msg">まだ役満は出ていません</p>';
    return;
  }
  const sorted = [...list].sort((a, b) => b.date.localeCompare(a.date));
  el.innerHTML = sorted.map(y => {
    const info = playerTeamMap[y.player];
    const metaHtml = info
      ? `<div class="yakuman-meta"><span>${info.teamName}</span><span>${info.owner}</span></div>`
      : '';
    return `
      <div class="yakuman-item">
        <div class="yakuman-top">
          <span class="yakuman-date">${y.date}</span>
          <span class="yakuman-player">${y.player}</span>
          <span class="yakuman-yaku">${y.yaku}</span>
          <span class="yakuman-score">${y.score.toLocaleString()}点</span>
        </div>
        ${metaHtml}
      </div>`;
  }).join('');
}

// ===== プレースホルダー画像生成 =====
function createPlaceholder() {
  const canvas = document.createElement('canvas');
  canvas.width = 60; canvas.height = 60;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#1e3828';
  ctx.fillRect(0, 0, 60, 60);
  ctx.fillStyle = '#7fad8f';
  ctx.font = '28px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('👤', 30, 32);
  return canvas.toDataURL();
}

// ===== メイン =====
async function init() {
  const [results, draft, yakuman] = await Promise.all([
    loadJSON('/data/results.json'),
    loadJSON('/data/draft.json'),
    loadJSON('/data/yakuman.json')
  ]);

  const placeholder = createPlaceholder();

  const matches = results.matches ?? [];
  const playerStats = buildPlayerStats(matches);
  const teamStats = buildTeamStats(draft.teams, playerStats);

  document.getElementById('last-updated').textContent =
    results.last_updated ? `最終更新: ${results.last_updated}` : '';

  // ランキング
  renderTeamRanking(teamStats);

  // チーム推移グラフ
  renderTeamChart(teamStats);

  // アワード
  renderAwards(playerStats, draft.teams);

  // 役満
  renderYakuman(yakuman, draft.teams);

  // プルダウン生成（選手推移）
  const select = document.getElementById('team-select');
  draft.teams.forEach((team, i) => {
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = team.name;
    select.appendChild(opt);
  });

  const updatePlayerChart = () => {
    const idx = parseInt(select.value);
    renderPlayerChart(draft.teams[idx], playerStats);
  };
  select.addEventListener('change', updatePlayerChart);
  updatePlayerChart();

  // 画像エラー時のフォールバック
  document.querySelectorAll('img').forEach(img => {
    img.addEventListener('error', () => { img.src = placeholder; });
  });
}

init().catch(console.error);
