// Matchmaking rules, shared by the page and by tests (node static/match.test.js).
(function (root) {
  const MODES = [1, 2, 3, 4];

  // N, any non-letter/non-digit separators (or none), "vs" | "v" | "x", separators, N.
  // Digits around it must not continue the number, so "11v11" or "1v12" don't count as 1v1.
  function modeRegex(n) {
    return new RegExp(`(?<!\\p{N})${n}[^\\p{L}\\p{N}]*(?:vs|v|x)[^\\p{L}\\p{N}]*${n}(?!\\p{N})`, "iu");
  }
  const REGEXES = Object.fromEntries(MODES.map(n => [n, modeRegex(n)]));

  // Which of 1..4 the title advertises ("3v3 or 4v4" -> [3, 4]).
  function titleModes(title) {
    return MODES.filter(n => REGEXES[n].test(title || ""));
  }

  // criteria: { modes: [1..4], eloMin: number|null, eloMax: number|null }
  function matchLobby(lobby, criteria) {
    if (!criteria.modes.length) return false;
    if (!titleModes(lobby.title).some(n => criteria.modes.includes(n))) return false;
    const elo = lobby.avg_elo;
    if (elo == null) return false;
    if (criteria.eloMin != null && elo < criteria.eloMin) return false;
    if (criteria.eloMax != null && elo > criteria.eloMax) return false;
    return true;
  }

  const api = { MODES, modeRegex, titleModes, matchLobby };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Matchmaking = api;
})(this);
