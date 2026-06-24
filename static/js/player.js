class Formatter {
  static time(seconds) {
    if (isNaN(seconds) || !isFinite(seconds)) return "0:00";
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    return `${min}:${sec.toString().padStart(2, "0")}`;
  }
}

class ArrayUtils {
  static shuffleInPlace(array, startIndex = 0) {
    for (let i = array.length - 1; i > startIndex; i--) {
      const j = startIndex + Math.floor(Math.random() * (i - startIndex + 1));
      [array[i], array[j]] = [array[j], array[i]];
    }
  }
}

class ApiService {
  static async request(method, endpoint, body = null) {
    const config = { method, headers: {} };
    if (body) {
      config.headers["Content-Type"] = "application/json";
      config.body = JSON.stringify(body);
    }
    const res = await fetch(endpoint, config);
    if (!res.ok) throw new Error(`API Error: ${res.statusText}`);
    return res.status !== 204 ? res.json() : null;
  }

  static get(endpoint) {
    return this.request("GET", endpoint);
  }
  static post(endpoint, body) {
    return this.request("POST", endpoint, body);
  }
  static delete(endpoint) {
    return this.request("DELETE", endpoint);
  }
}

class QueueManager {
  constructor() {
    this.tracks = [];
    this.index = -1;
    this.mode = "all";
    this.isPlaylistMode = false;
  }

  setContext(tracks, startIndex, isPlaylist, shouldShuffle) {
    this.isPlaylistMode = isPlaylist;

    if (!shouldShuffle || tracks.length <= 1) {
      this.tracks = [...tracks];
      this.index = startIndex;
      return;
    }

    const current = tracks[startIndex];
    const rest = tracks.filter((_, i) => i !== startIndex);

    ArrayUtils.shuffleInPlace(rest);

    this.tracks = [current, ...rest];
    this.index = 0;
  }

  getCurrent() {
    return this.tracks[this.index] || null;
  }

  moveTo(newIndex) {
    if (newIndex >= 0 && newIndex < this.tracks.length) {
      this.index = newIndex;
      return true;
    }
    return false;
  }

  shuffleUpcoming() {
    if (
      this.tracks.length <= 1 ||
      this.index < 0 ||
      this.index >= this.tracks.length - 1
    )
      return;
    ArrayUtils.shuffleInPlace(this.tracks, this.index + 1);
  }

  nextIndex() {
    if (this.index < this.tracks.length - 1) return this.index + 1;
    return this.isPlaylistMode && this.tracks.length > 0 ? 0 : -1;
  }

  prevIndex() {
    return this.index > 0 ? this.index - 1 : -1;
  }

  appendUnique(newTracks) {
    const existingIds = new Set(this.tracks.map((t) => t.id));
    const unique = newTracks.filter((t) => !existingIds.has(t.id));
    this.tracks.push(...unique);
  }

  removeTrack(trackId) {
    this.tracks = this.tracks.filter((t) => t.id !== trackId);
  }
}

class AudioController {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById("audioElement");
    this.playIcon = document.getElementById("playIcon");
    this.volumeIcon = document.getElementById("volumeIcon");
    this.seekSlider = document.getElementById("seekSlider");
    this.volumeSlider = document.getElementById("volumeSlider");
    this.retryCount = 0;
    this.bindEvents();
  }

  bindEvents() {
    this.el.addEventListener("timeupdate", () => this.updateProgress());
    this.el.addEventListener("loadedmetadata", () => this.updateDuration());
    this.el.addEventListener("ended", () => this.app.playNext());
    this.el.addEventListener("error", () => this.handleStreamError());
  }

  play(url = null) {
    if (url) {
      this.retryCount = 0;
      this.el.pause();
      this.el.src = "";
      this.el.load();
      this.el.src = url;
    }

    const promise = this.el.play();
    if (promise) {
      promise
        .then(() => (this.playIcon.className = "bi bi-pause-fill"))
        .catch(() => setTimeout(() => this.play(), 500));
    }
  }

  handleStreamError() {
    const err = this.el.error;

    if (err && err.code === 2 && this.el.src) {
      if (this.retryCount < 3) {
        this.retryCount++;
        const droppedTime = this.el.currentTime;
        console.warn(
          `Stream dropped. Reconnecting (${this.retryCount}/3) at ${droppedTime}s...`,
        );

        const currentUrl = this.el.src;
        this.el.pause();
        this.el.src = "";
        this.el.load();
        this.el.src = currentUrl;
        this.el.currentTime = droppedTime;
        this.play();
      } else {
        console.error("Stream unrecoverable. Skipping to next track.");
        this.app.playNext();
      }
    } else if (err && err.code === 4) {
      console.error("Stream failed to load. Skipping to next track.");
      this.app.playNext();
    }
  }

  pause() {
    this.el.pause();
    this.playIcon.className = "bi bi-play-fill";
  }

  togglePlay() {
    if (!this.el.src) return;
    this.el.paused ? this.play() : this.pause();
  }

  setVolume(vol) {
    const clamped = Math.max(0, Math.min(1, vol));
    this.el.volume = clamped;
    this.volumeSlider.value = clamped;

    if (clamped === 0)
      this.volumeIcon.className =
        "bi bi-volume-mute-fill fs-5 me-2 text-danger";
    else if (clamped < 0.5)
      this.volumeIcon.className = "bi bi-volume-down-fill fs-5 me-2";
    else this.volumeIcon.className = "bi bi-volume-up-fill fs-5 me-2";
  }

  adjustVolume(delta) {
    this.setVolume(this.el.volume + delta);
  }

  toggleMute() {
    this.setVolume(this.el.volume > 0 ? 0 : 1);
  }

  seekToPercent(percent) {
    if (this.el.duration)
      this.el.currentTime = this.el.duration * (percent / 100);
  }

  updateProgress() {
    if (!this.el.duration) return;
    this.seekSlider.value = (this.el.currentTime / this.el.duration) * 100;
    document.getElementById("currentTime").innerText = Formatter.time(
      this.el.currentTime,
    );
  }

  updateDuration() {
    document.getElementById("durationTime").innerText = Formatter.time(
      this.el.duration,
    );
  }
}

class PassiveScoreTracker {
  constructor() {
    this.interval = null;
    this.activeTrackId = null;
  }

  start(trackId, audioEl, onUpdate) {
    this.stop();
    this.activeTrackId = trackId;
    this.interval = setInterval(async () => {
      if (audioEl.paused || !this.activeTrackId) return;

      try {
        const res = await ApiService.post(
          `/api/weight/passive/${this.activeTrackId}`,
          { seconds: 10.0 },
        );
        if (res.status === "success" && res.new_score !== undefined) {
          onUpdate(this.activeTrackId, res.new_score);
        }
      } catch (e) {
        console.error("Score tracker error", e);
      }
    }, 10000);
  }

  stop() {
    if (this.interval) clearInterval(this.interval);
  }
}

class SearchAutocomplete {
  constructor(app) {
    this.app = app;
    this.input = document.getElementById("searchInput");
    this.btn = document.getElementById("searchBtn");
    this.historyKey = "mtube_search_history";
    this.debounceTimer = null;

    if (!this.input) return;
    this.setupUI();
    this.bindEvents();
  }

  setupUI() {
    this.inputGroup = this.input.closest(".input-group");
    if (this.inputGroup) {
      this.inputGroup.classList.add("position-relative");
      this.dropdown = document.createElement("ul");
      this.dropdown.className = "suggestions-dropdown d-none";
      this.inputGroup.appendChild(this.dropdown);
    }
  }

  bindEvents() {
    this.input.addEventListener("input", (e) => this.onInput(e.target.value));
    this.input.addEventListener("focus", () => this.onInput(this.input.value));

    document.addEventListener("click", (e) => {
      if (!this.input.contains(e.target) && !this.dropdown.contains(e.target)) {
        this.hide();
      }
    });
  }

  onInput(query) {
    clearTimeout(this.debounceTimer);
    const trimmed = query.trim();

    if (!trimmed) {
      this.showHistory();
      return;
    }

    this.debounceTimer = setTimeout(() => this.fetchSuggestions(trimmed), 300);
  }

  async fetchSuggestions(query) {
    try {
      const res = await fetch(
        `/api/search/suggestions?q=${encodeURIComponent(query)}`,
      );
      const json = await res.json();
      if (json.status === "success" && json.data.length > 0) {
        this.render(json.data, "Suggestions", "bi-search");
      } else {
        this.hide();
      }
    } catch (err) {
      console.error("Autocomplete fetch failed:", err);
    }
  }

  showHistory() {
    const history = JSON.parse(localStorage.getItem(this.historyKey) || "[]");
    if (history.length > 0) {
      this.render(history, "Recent Searches", "bi-clock-history");
    } else {
      this.hide();
    }
  }

  saveHistory(query) {
    const trimmed = query.trim();
    if (!trimmed) return;

    let history = JSON.parse(localStorage.getItem(this.historyKey) || "[]");
    history = history.filter((item) => item !== trimmed);
    history.unshift(trimmed);
    if (history.length > 10) history.pop();

    localStorage.setItem(this.historyKey, JSON.stringify(history));
    this.hide();
  }

  render(items, headerText, iconClass) {
    this.dropdown.innerHTML = `<li class="suggestion-header">${headerText}</li>`;

    items.forEach((item) => {
      const li = document.createElement("li");
      li.className = "suggestion-item";
      li.innerHTML = `<i class="bi ${iconClass}"></i><span>${item}</span>`;

      li.addEventListener("click", () => {
        this.input.value = item;
        this.saveHistory(item);
        this.hide();
        this.app.ui.switchMainView("home");
        this.app.handleSearch();
      });

      this.dropdown.appendChild(li);
    });

    this.dropdown.classList.remove("d-none");
  }

  hide() {
    this.dropdown.classList.add("d-none");
  }
}

class UIBuilder {
  static getThumbnail(url) {
    const icon = "bi bi-music-note-beamed fs-4 text-secondary me-3";
    return url
      ? `<img src="${url}" class="cover-img me-3" alt="Thumb" onerror="this.replaceWith(Object.assign(document.createElement('i'), {className: '${icon}'}))">`
      : `<i class="${icon}"></i>`;
  }

  static createPlaylistItemHTML(id, name, iconClass, isActive) {
    const activeClass = isActive ? "active" : "";
    const safeName = name.replace(/'/g, "\\'");
    return `<button class="list-group-item list-group-item-action playlist-item ${activeClass}" data-playlist-id="${id}" onclick="app.selectPlaylist('${id}', '${safeName}')"><i class="${iconClass} me-2"></i> ${name}</button>`;
  }

  static createTrackElement(track, index, onClick, onRemove = null) {
    const div = document.createElement("div");
    div.className =
      "list-group-item result-item d-flex align-items-center text-light";
    div.dataset.index = index;
    div.dataset.trackId = track.id;

    const score = parseFloat(track.score) || 0.0;
    const durationHtml = track.duration
      ? `<small class="text-muted ms-3" style="min-width: 35px; text-align: right;">${Formatter.time(track.duration)}</small>`
      : "";

    div.innerHTML = `
            ${this.getThumbnail(track.thumbnail)}
            <div class="overflow-hidden flex-grow-1 pe-2">
                <div class="text-truncate" style="font-size: 0.9rem; font-weight: 500;">${track.title}</div>
                <small class="text-muted text-truncate d-block">${track.uploader}</small>
            </div>
            <div class="d-flex align-items-center flex-shrink-0">
                <span class="score-badge" data-track-id="${track.id}">${score.toFixed(1)}</span>
                ${durationHtml}
            </div>
        `;

    if (onRemove) {
      const btn = document.createElement("button");
      btn.className = "action-btn text-danger ms-3";
      btn.innerHTML = '<i class="bi bi-x-lg"></i>';
      btn.onclick = (e) => {
        e.stopPropagation();
        onRemove(track.id);
      };
      div.querySelector(".flex-shrink-0").appendChild(btn);
    }

    div.addEventListener("click", () => onClick(index, track));
    return div;
  }
}

class UIManager {
  constructor(app) {
    this.app = app;
    this.bindEvents();
  }

  bindEvents() {
    this.bindNavigation();
    this.bindSearch();
    this.bindPlaylists();
    this.bindQueue();
    this.bindPlayer();
    this.bindKeyboardShortcuts();
  }

  bindNavigation() {
    const bind = (id, handler) =>
      document.getElementById(id)?.addEventListener("click", handler);
    bind("brandBtn", () => this.app.resetToSupermix());
    bind("navHomeBtn", () => this.app.resetToSupermix());
    bind("navPlaylistsBtn", () => this.switchMainView("playlists"));
    bind("navHistoryBtn", () => this.switchMainView("history"));
    bind("toggleSidebarBtn", () => this.toggleSidebar());
  }

  bindSearch() {
    this.autocomplete = new SearchAutocomplete(this.app);

    document.getElementById("searchBtn")?.addEventListener("click", () => {
      const val = document.getElementById("searchInput").value;
      if (val) this.autocomplete.saveHistory(val);
      this.app.handleSearch();
    });

    document.getElementById("searchInput")?.addEventListener("keyup", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        e.target.blur();
        if (e.target.value) this.autocomplete.saveHistory(e.target.value);
        this.switchMainView("home");
        this.app.handleSearch();
      }
    });
  }

  bindPlaylists() {
    const bind = (id, handler) =>
      document.getElementById(id)?.addEventListener("click", handler);
    bind("openCreatePlaylistModalBtn", () => this.openCreatePlaylistModal());
    bind("submitCreatePlaylistBtn", () => this.app.submitCreatePlaylist());
    bind("playAllBtn", () => this.app.playCurrentPlaylist());
    bind("addPlaylistActionBtn", () => this.openAddToPlaylistModal());
    bind("saveToPlaylistBtn", () => this.app.saveToPlaylist());
  }

  bindQueue() {
    const bind = (id, handler) =>
      document.getElementById(id)?.addEventListener("click", handler);
    bind("upNextTabBtn", () => this.switchSidebarTab("upnext"));
    bind("lyricsTabBtn", () => this.switchSidebarTab("lyrics"));
    bind("queueModeAllBtn", (e) => this.app.setQueueMode("all", e.target));
    bind("queueModeFamiliarBtn", (e) =>
      this.app.setQueueMode("familiar", e.target),
    );

    document
      .getElementById("autoShuffleSwitch")
      ?.addEventListener("change", (e) => {
        if (e.target.checked) {
          this.app.queue.shuffleUpcoming();
          this.app.renderQueue();
        }
      });
  }

  bindPlayer() {
    const bind = (id, handler) =>
      document.getElementById(id)?.addEventListener("click", handler);
    bind("favActionBtn", () => this.app.handlePlayerAction("favorite"));
    bind("upvoteActionBtn", () => this.app.handlePlayerAction("upvote"));
    bind("downvoteActionBtn", () => this.app.handlePlayerAction("downvote"));
    bind("trashActionBtn", () => this.app.handlePlayerAction("trash"));
    bind("prevBtn", () => this.app.playPrevious());
    bind("playPauseBtn", () => this.app.audio.togglePlay());
    bind("nextBtn", () => this.app.playNext());
    bind("volumeIcon", () => this.app.audio.toggleMute());

    document
      .getElementById("volumeSlider")
      ?.addEventListener("input", (e) =>
        this.app.audio.setVolume(parseFloat(e.target.value)),
      );
    document
      .getElementById("seekSlider")
      ?.addEventListener("input", (e) =>
        this.app.audio.seekToPercent(parseFloat(e.target.value)),
      );
  }

  bindKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
      if (
        ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)
      )
        return;
      const actions = {
        Space: () => this.app.audio.togglePlay(),
        ArrowRight: () => this.app.playNext(),
        ArrowLeft: () => this.app.playPrevious(),
        ArrowUp: () => this.app.audio.adjustVolume(0.05),
        ArrowDown: () => this.app.audio.adjustVolume(-0.05),
        KeyM: () => this.app.audio.toggleMute(),
      };
      if (actions[e.code]) {
        e.preventDefault();
        actions[e.code]();
      }
    });
  }

  switchMainView(viewName) {
    document
      .getElementById("homeView")
      .classList.toggle("d-none", viewName !== "home");
    document
      .getElementById("historyView")
      .classList.toggle("d-none", viewName !== "history");
    document
      .getElementById("playlistsView")
      .classList.toggle("d-none", viewName !== "playlists");

    document
      .getElementById("navHomeBtn")
      .classList.toggle("active", viewName === "home");
    document
      .getElementById("navHistoryBtn")
      .classList.toggle("active", viewName === "history");
    document
      .getElementById("navPlaylistsBtn")
      .classList.toggle("active", viewName === "playlists");

    if (viewName === "history") this.app.loadHistory();
    if (viewName === "playlists") this.renderPlaylistsSidebar();
  }

  switchSidebarTab(tabName) {
    document
      .getElementById("upNextTabBtn")
      .classList.toggle("active", tabName === "upnext");
    document
      .getElementById("lyricsTabBtn")
      .classList.toggle("active", tabName === "lyrics");
    document
      .getElementById("upNextWrapper")
      .classList.toggle("d-none", tabName !== "upnext");
    document
      .getElementById("lyricsContainer")
      .classList.toggle("d-none", tabName !== "lyrics");
  }

  toggleSidebar() {
    const sidebar = document.getElementById("sidebar");
    sidebar.classList.toggle("open");
    if (sidebar.classList.contains("open")) this.highlightActiveTrack();
  }

  toggleLoadingState(isLoading) {
    document.getElementById("loading").classList.toggle("d-none", !isLoading);
    if (isLoading) document.getElementById("resultsContainer").innerHTML = "";
  }

  renderTrackList(
    containerId,
    tracks,
    onClickCallback,
    onRemoveCallback = null,
  ) {
    const container = document.getElementById(containerId);
    container.innerHTML = "";

    if (tracks.length === 0) {
      container.innerHTML =
        '<div class="text-center text-muted my-4">No data available.</div>';
      return;
    }

    tracks.forEach((item, index) => {
      const div = UIBuilder.createTrackElement(
        item,
        index,
        onClickCallback,
        onRemoveCallback,
      );
      container.appendChild(div);
    });
    this.highlightActiveTrack();
  }

  renderPlaylistsSidebar() {
    const container = document.getElementById("playlistSidebarList");

    let html = UIBuilder.createPlaylistItemHTML(
      "favorites",
      "Favorites",
      "bi bi-heart-fill text-danger",
      this.app.activePlaylistId === "favorites",
    );

    this.app.userPlaylists.forEach((p) => {
      html += UIBuilder.createPlaylistItemHTML(
        p.id,
        p.name,
        "bi bi-music-note-list",
        this.app.activePlaylistId === p.id,
      );
    });

    container.innerHTML = html;

    const activeName =
      this.app.activePlaylistId === "favorites"
        ? "Favorites"
        : this.app.userPlaylists.find((p) => p.id === this.app.activePlaylistId)
            ?.name;

    this.app.selectPlaylist(this.app.activePlaylistId, activeName);
  }

  updatePlayerBar(track) {
    document.getElementById("nowPlayingText").innerText = track.title;
    document.getElementById("nowPlayingUploader").innerText = track.uploader;
    document.getElementById("playerThumbnailContainer").innerHTML =
      UIBuilder.getThumbnail(track.thumbnail);
    document.getElementById("playerActions").classList.remove("d-none");

    const favIcon = document.getElementById("playerFavIcon");
    favIcon.className = track.is_favorited
      ? "bi bi-heart-fill favorited"
      : "bi bi-heart";

    const filters = document.getElementById("queueModeFilters");
    this.app.queue.isPlaylistMode
      ? filters.classList.add("d-none")
      : filters.classList.remove("d-none");

    this.highlightActiveTrack();
  }

  highlightActiveTrack() {
    const currentTrack = this.app.queue.getCurrent();
    if (!currentTrack) return;

    document.querySelectorAll(".result-item").forEach((item) => {
      item.classList.remove("active");
      const isSidebarItem = item.closest("#sidebar");

      if (
        isSidebarItem &&
        parseInt(item.dataset.index) === this.app.queue.index
      ) {
        item.classList.add("active");
        if (this.isElementVisible(item))
          item.scrollIntoView({ behavior: "smooth", block: "nearest" });
      } else if (!isSidebarItem && item.dataset.trackId === currentTrack.id) {
        item.classList.add("active");
      }
    });
  }

  isElementVisible(el) {
    if (el.closest(".d-none")) return false;
    const sidebar = el.closest("#sidebar");
    return !(sidebar && !sidebar.classList.contains("open"));
  }

  openCreatePlaylistModal() {
    document.getElementById("newPlaylistNameInput").value = "";
    this.createModal = new bootstrap.Modal(
      document.getElementById("createPlaylistModal"),
    );
    this.createModal.show();
  }

  openAddToPlaylistModal() {
    if (!this.app.queue.getCurrent()) return;
    const select = document.getElementById("playlistSelect");
    select.innerHTML = "";
    this.app.userPlaylists.forEach(
      (p) => (select.innerHTML += `<option value="${p.id}">${p.name}</option>`),
    );
    if (this.app.userPlaylists.length === 0)
      select.innerHTML =
        "<option disabled>No custom playlists available</option>";

    this.addModal = new bootstrap.Modal(
      document.getElementById("playlistModal"),
    );
    this.addModal.show();
  }
}

class AppController {
  constructor() {
    this.audio = new AudioController(this);
    this.queue = new QueueManager();
    this.tracker = new PassiveScoreTracker();
    this.ui = new UIManager(this);

    this.currentViewTracks = [];
    this.activePlaylistTracks = [];
    this.userPlaylists = [];
    this.activePlaylistId = "favorites";
    this.isFetchingRelated = false;

    this.cachedModes = { all: null, familiar: null };
    this.queue.mode = "all";
  }

  async init() {
    this.ui.switchMainView("home");
    await this.loadPlaylists();
    this.loadHomeRecommendations();
  }

  resetToSupermix() {
    const searchInput = document.getElementById("searchInput");
    const currentTitle = document.getElementById("homeSectionTitle").innerText;

    this.ui.switchMainView("home");

    if (searchInput.value.trim() !== "" || !currentTitle.includes("Supermix")) {
      searchInput.value = "";
      this.loadHomeRecommendations();
    }
  }

  async loadPlaylists() {
    try {
      const res = await ApiService.get("/api/playlist/");
      this.userPlaylists = res.data || [];
    } catch (e) {
      console.error("Failed fetching playlists", e);
    }
  }

  async loadHomeRecommendations() {
    const searchInput = document.getElementById("searchInput");
    if (searchInput.value.trim() !== "") return;

    this.ui.toggleLoadingState(true);
    document.getElementById("homeSectionTitle").innerHTML =
      '<i class="bi bi-shuffle text-warning me-2"></i>Your Supermix';

    try {
      const res = await ApiService.get("/api/recommendation/mix");
      this.currentViewTracks = res.data;
      this.ui.renderTrackList("resultsContainer", res.data, (idx) =>
        this.playFromContext(idx, res.data, false),
      );
    } catch (error) {
      console.error("Home error", error);
    } finally {
      this.ui.toggleLoadingState(false);
    }
  }

  async handleSearch() {
    const query = document.getElementById("searchInput").value.trim();
    if (!query) return this.loadHomeRecommendations();

    document.getElementById("homeSectionTitle").innerHTML =
      '<i class="bi bi-search me-2"></i>Search Results';
    this.ui.toggleLoadingState(true);

    try {
      const res = await ApiService.get(
        `/api/search/?query=${encodeURIComponent(query)}`,
      );
      this.currentViewTracks = res.data;
      this.ui.renderTrackList("resultsContainer", res.data, (idx) =>
        this.playFromContext(idx, res.data, false),
      );
    } catch (error) {
      console.error("Search failed", error);
    } finally {
      this.ui.toggleLoadingState(false);
    }
  }

  async loadHistory() {
    const container = document.getElementById("historyContainer");
    container.innerHTML =
      '<div class="text-center mt-4"><div class="spinner-border text-secondary p-2"></div></div>';
    try {
      const res = await ApiService.get("/api/history/");
      this.ui.renderTrackList("historyContainer", res.data, (idx) =>
        this.playFromContext(idx, res.data, false),
      );
    } catch (e) {
      container.innerHTML =
        '<div class="text-muted text-center mt-4">Failed to load history.</div>';
    }
  }

  async selectPlaylist(id, name) {
    if (!name) return;
    this.activePlaylistId = id;
    document.getElementById("currentPlaylistTitle").innerText = name;

    document
      .querySelectorAll("#playlistSidebarList button")
      .forEach((b) => b.classList.remove("active"));

    const activeBtn = document.querySelector(
      `#playlistSidebarList button[data-playlist-id="${id}"]`,
    );
    if (activeBtn) activeBtn.classList.add("active");

    const container = document.getElementById("playlistTracksContainer");
    container.innerHTML =
      '<div class="text-center mt-4"><div class="spinner-border text-secondary"></div></div>';

    const endpoint =
      id === "favorites"
        ? "/api/playlist/favorites"
        : `/api/playlist/${id}/tracks`;
    try {
      const res = await ApiService.get(endpoint);
      this.activePlaylistTracks = res.data;

      const onRemove =
        id !== "favorites"
          ? (trackId) => this.removeTrackFromPlaylist(id, trackId)
          : null;
      this.ui.renderTrackList(
        "playlistTracksContainer",
        res.data,
        (idx) => this.playFromContext(idx, this.activePlaylistTracks, true),
        onRemove,
      );
    } catch (e) {
      console.error("Playlist load failed", e);
    }
  }

  async submitCreatePlaylist() {
    const name = document.getElementById("newPlaylistNameInput").value.trim();
    if (!name) return;
    try {
      await ApiService.post("/api/playlist/", { name });
      this.ui.createModal?.hide();
      await this.loadPlaylists();
      this.ui.renderPlaylistsSidebar();
    } catch (e) {
      console.error("Failed creating playlist", e);
    }
  }

  async saveToPlaylist() {
    const pId = document.getElementById("playlistSelect").value;
    const track = this.queue.getCurrent();
    if (!pId || !track) return;

    try {
      await ApiService.post(`/api/playlist/${pId}/tracks`, track);
      this.ui.addModal?.hide();
      if (this.activePlaylistId === pId)
        this.selectPlaylist(
          pId,
          document.getElementById("currentPlaylistTitle").innerText,
        );
    } catch (e) {
      console.error("Failed saving track", e);
    }
  }

  async removeTrackFromPlaylist(playlistId, trackId) {
    try {
      await ApiService.delete(`/api/playlist/${playlistId}/tracks/${trackId}`);
      this.selectPlaylist(
        playlistId,
        document.getElementById("currentPlaylistTitle").innerText,
      );
    } catch (e) {
      console.error("Failed to remove", e);
    }
  }

  playCurrentPlaylist() {
    if (this.activePlaylistTracks.length > 0)
      this.playFromContext(0, this.activePlaylistTracks, true);
  }

  async setQueueMode(mode, btnElement) {
    this.queue.mode = mode;

    document
      .querySelectorAll(".chip-btn")
      .forEach((b) => b.classList.remove("active"));
    if (btnElement) btnElement.classList.add("active");

    const currentTrack = this.queue.getCurrent();
    if (!currentTrack || this.queue.isPlaylistMode) return;

    if (this.cachedModes[mode]) {
      this.restoreCachedQueue(this.cachedModes[mode]);
    } else {
      await this.rebuildUpNextQueue(currentTrack.id);
    }
  }

  playFromContext(index, trackList, isPlaylist = false) {
    const shouldShuffle =
      document.getElementById("autoShuffleSwitch")?.checked ?? true;
    this.queue.setContext(trackList, index, isPlaylist, shouldShuffle);

    this.cachedModes = { all: null, familiar: null };
    if (!isPlaylist) this.cachedModes[this.queue.mode] = [...this.queue.tracks];

    this.renderQueue();
    this.executePlay();
  }

  playFromQueue(index) {
    if (this.queue.moveTo(index)) this.executePlay();
  }

  playNext() {
    const nextIdx = this.queue.nextIndex();
    if (nextIdx >= 0) this.playFromQueue(nextIdx);
  }

  playPrevious() {
    const prevIdx = this.queue.prevIndex();
    if (prevIdx >= 0) this.playFromQueue(prevIdx);
  }

  executePlay() {
    const track = this.queue.getCurrent();
    if (!track) return;

    this.ui.updatePlayerBar(track);
    this.fetchLyrics(track);
    this.tracker.start(track.id, this.audio.el, (tId, score) =>
      this.syncTrackState(tId, score),
    );

    if (
      this.queue.index >= this.queue.tracks.length - 3 &&
      !this.queue.isPlaylistMode
    ) {
      this.fetchAndAppendRelated(track.id);
    }

    this.audio.play(`/api/stream/${track.id}`);
    ApiService.post("/api/history/", track).catch((e) =>
      console.error("History err", e),
    );
  }

  renderQueue() {
    this.ui.renderTrackList("upNextContainer", this.queue.tracks, (idx) =>
      this.playFromQueue(idx),
    );
  }

  async fetchLyrics(track) {
    const container = document.getElementById("lyricsContainer");
    container.innerHTML =
      '<div class="text-center mt-4"><div class="spinner-border text-secondary spinner-border-sm"></div></div>';
    try {
      const params = new URLSearchParams({
        title: track.title,
        video_id: track.id,
      });
      const res = await ApiService.get(`/api/lyrics/?${params.toString()}`);
      container.innerText = res.data;
    } catch (e) {
      container.innerHTML =
        '<div class="text-muted text-center mt-4">Lyrics not found.</div>';
    }
  }

  async fetchAndAppendRelated(videoId) {
    if (this.isFetchingRelated || this.queue.isPlaylistMode) return;
    this.isFetchingRelated = true;
    try {
      const res = await ApiService.get(
        `/api/recommendation/related/${videoId}?mode=${this.queue.mode}`,
      );
      if (res.data && res.data.length > 0) {
        this.queue.appendUnique(res.data);
        this.cachedModes[this.queue.mode] = [...this.queue.tracks];
        this.renderQueue();
      }
    } catch (e) {
      console.error("Related error", e);
    } finally {
      this.isFetchingRelated = false;
    }
  }

  async rebuildUpNextQueue(videoId) {
    if (this.isFetchingRelated || this.queue.isPlaylistMode) return;

    this.isFetchingRelated = true;
    const container = document.getElementById("upNextContainer");
    container.innerHTML =
      '<div class="text-center mt-4"><div class="spinner-border text-secondary"></div></div>';

    try {
      const res = await ApiService.get(
        `/api/recommendation/related/${videoId}?mode=${this.queue.mode}`,
      );
      const current = this.queue.getCurrent();

      const newTracks = [current, ...(res.data || [])];
      this.cachedModes[this.queue.mode] = newTracks;

      this.restoreCachedQueue(newTracks);
    } catch (e) {
      console.error("Cache build failed", e);
      container.innerHTML =
        '<div class="text-muted text-center mt-4">Failed to load recommendations.</div>';
    } finally {
      this.isFetchingRelated = false;
    }
  }

  restoreCachedQueue(trackList) {
    this.queue.tracks = [...trackList];
    if (this.queue.index >= this.queue.tracks.length) this.queue.index = 0;
    this.renderQueue();
  }

  async handlePlayerAction(action) {
    const current = this.queue.getCurrent();
    if (!current) return;

    try {
      const res = await ApiService.post(`/api/weight/action/${current.id}`, {
        action,
      });
      if (action === "trash") {
        this.queue.removeTrack(current.id);
        this.renderQueue();
        this.playNext();
        return;
      }

      this.syncTrackState(current.id, res.new_score, action);
      if (
        action === "favorite" &&
        this.activePlaylistId === "favorites" &&
        !document.getElementById("playlistsView").classList.contains("d-none")
      ) {
        this.selectPlaylist("favorites", "Favorites");
      }
    } catch (e) {
      console.error("Action failed", e);
    }
  }

  syncTrackState(trackId, newScore, action = null) {
    const safeScore = parseFloat(newScore) || 0.0;
    let refTrack =
      this.queue.tracks.find((t) => t.id === trackId) ||
      this.currentViewTracks.find((t) => t.id === trackId);
    if (!refTrack) return;

    const newFavState =
      action === "favorite" ? !refTrack.is_favorited : refTrack.is_favorited;

    [
      this.currentViewTracks,
      this.queue.tracks,
      this.activePlaylistTracks,
    ].forEach((list) => {
      if (list)
        list.forEach((t) => {
          if (t.id === trackId) {
            t.score = safeScore;
            t.is_favorited = newFavState;
          }
        });
    });

    document
      .querySelectorAll(`.score-badge[data-track-id="${trackId}"]`)
      .forEach((badge) => (badge.innerText = safeScore.toFixed(1)));

    if (trackId === this.queue.getCurrent()?.id) {
      document.getElementById("playerFavIcon").className = newFavState
        ? "bi bi-heart-fill favorited"
        : "bi bi-heart";
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.app = new AppController();
  window.app.init();
});
