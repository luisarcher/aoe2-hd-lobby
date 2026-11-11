// Run: node static/match.test.js
const assert = require("assert");
const { titleModes, matchLobby } = require("./match.js");

const cases = [
  ["1v1", [1]], ["1 v 1", [1]], ["1vs1", [1]], ["1 VS 1", [1]], ["1 vs. 1", [1]], ["1x1", [1]],
  ["1 X 1", [1]], ["1-v-1 arabia", [1]], ["anyone can join 1v1", [1]], ["1v 1", [1]],
  ["1vs1 1500 to 1600 random civs and maps", [1]], ["1vs1, 1000-1100, green ping, say 30", [1]],
  ["RM 1v1 2v2 under 1300", [1, 2]], ["3v3 or 4v4", [3, 4]], ["3 VS 3 GREEN UP BF EU NOOBS", [3]],
  ["4vs4 bf <1400 no forest burnıng no siege", [4]], ["dm oasis 2v2+++2dm oasis 2v2+++2", [2]],
  ["michi michi michi michi 3v3 DM", [3]], ["Water prison 2v2 3v3", [2, 3]],
  ["11v11", []], ["1v12", []], ["21v1", []], ["1v2", []], ["4v1", []], ["1200 - 1400 1 v 1", [1]],
  ["RM OASIS GOLD", []], ["Partie de Mister Bobo", []], ["", []],
];
for (const [title, want] of cases) assert.deepStrictEqual(titleModes(title), want, `"${title}"`);

const lobby = { title: "1v1 arabia", avg_elo: 1700 };
assert.ok(matchLobby(lobby, { modes: [1], eloMin: 1600, eloMax: 1800 }));
assert.ok(matchLobby(lobby, { modes: [1], eloMin: 1700, eloMax: 1700 }), "range is inclusive");
assert.ok(!matchLobby(lobby, { modes: [1], eloMin: 1750, eloMax: 1800 }));
assert.ok(!matchLobby(lobby, { modes: [2], eloMin: null, eloMax: null }));
assert.ok(!matchLobby({ title: "1v1", avg_elo: null }, { modes: [1], eloMin: null, eloMax: null }));
assert.ok(matchLobby({ title: "3v3 or 4v4", avg_elo: 1500 }, { modes: [4], eloMin: 1400, eloMax: 1600 }));
console.log(`all ${cases.length + 6} checks passed`);
