const _owners = new Map(); // sessionId → principal

function register(sessionId, principal) {
  _owners.set(sessionId, principal);
}

function deregister(sessionId) {
  _owners.delete(sessionId);
}

function check(sessionId, principal) {
  const owner = _owners.get(sessionId);
  return owner !== undefined && owner === principal;
}

function clear() {
  _owners.clear();
}

module.exports = { register, deregister, check, clear };
