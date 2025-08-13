/**
 * Type-specific renderers for JSON objects
 */

/**
 * Base class for type-specific renderers
 */
export class TypeRenderer {
  /**
   * @param {JsonRenderer} jsonRenderer
   */
  constructor(jsonRenderer) {
    this.jsonRenderer = jsonRenderer;
  }
  /**
   * @param {Object} item
   * @returns {HTMLElement|null}
   */
  render(item) {
    return null; // to be implemented by subclasses
  }
}

/**
 * ────────────────────────────
 * Real‑estate listings
 * ────────────────────────────
 */
export class RealEstateRenderer extends TypeRenderer {
  static get supportedTypes() {
    return [
      "SingleFamilyResidence",
      "Apartment",
      "Townhouse",
      "House",
      "Condominium",
      "RealEstateListing",
    ];
  }

  render(item) {
    const element = this.jsonRenderer.createDefaultItemHtml(item);
    const contentDiv = element.querySelector(".item-content");
    if (!contentDiv) return element;

    const detailsDiv = this.jsonRenderer.possiblyAddExplanation(item, contentDiv, true);
    if (!detailsDiv) return element;

    detailsDiv.className = "item-real-estate-details";

    const schema = item.schema_object;
    if (!schema) return element;

    const price = schema.price;
    const address = schema.address || {};
    const numBedrooms = schema.numberOfRooms;
    const numBathrooms = schema.numberOfBathroomsTotal;
    const sqft = schema.floorSize?.value;

    let priceValue = price;
    if (typeof price === "object") {
      priceValue = price.price || price.value || price;
      if (typeof priceValue === "number") {
        priceValue = Math.round(priceValue / 100000) * 100000;
        priceValue = priceValue.toLocaleString("en-US");
      }
    }

    const streetAddress = address.streetAddress || "";
    const addressLocality = address.addressLocality || "";
    detailsDiv.appendChild(this.jsonRenderer.makeAsSpan(`${streetAddress}, ${addressLocality}`));
    detailsDiv.appendChild(document.createElement("br"));

    const bedroomsText = numBedrooms || "0";
    const bathroomsText = numBathrooms || "0";
    const sqftText = sqft || "0";
    detailsDiv.appendChild(
      this.jsonRenderer.makeAsSpan(`${bedroomsText} bedrooms, ${bathroomsText} bathrooms, ${sqftText} sqft`)
    );
    detailsDiv.appendChild(document.createElement("br"));

    if (priceValue) {
      detailsDiv.appendChild(this.jsonRenderer.makeAsSpan(`Listed at ${priceValue}`));
    }

    return element;
  }
}

/**
 * ────────────────────────────
 * Podcast episodes
 * ────────────────────────────
 */
export class PodcastEpisodeRenderer extends TypeRenderer {
  static get supportedTypes() {
    return ["PodcastEpisode"];
  }

  render(item) {
    const element = this.jsonRenderer.createDefaultItemHtml(item);
    const contentDiv = element.querySelector(".item-content");
    if (!contentDiv) return element;
    this.jsonRenderer.possiblyAddExplanation(item, contentDiv, true);
    return element;
  }
}

/**
 * ────────────────────────────
 * Health cards (MedicalOrganization etc.)
 *  - MedicalSpecialty pills
 *  - Postcode pill (deep scan + @id deref + URL fallback)
 * ────────────────────────────
 */
export class HealthCardRenderer extends TypeRenderer {
  static get supportedTypes() {
    return ["MedicalOrganization", "Place", "Service", "Organization", "LocalBusiness", "Hospital"];
  }

  render(item) {
    const element = this.jsonRenderer.createDefaultItemHtml(item);
    const content = element.querySelector(".item-content") || element;

    // Normalize schema_object if it arrived as a string
    if (typeof item.schema_object === "string") {
      try { item.schema_object = JSON.parse(item.schema_object); } catch {}
    }

    // Collect nodes
    const nodes = Array.isArray(item.schema_object)
      ? item.schema_object.filter(Boolean)
      : item.schema_object
      ? [item.schema_object]
      : [];

    // Build an @id index so we can follow references
    const idIndex = buildIdIndex(nodes);

    // Extract specialty names
    const specialtyNames = Array.from(
      new Set(
        nodes.flatMap(n => extractSpecialties(n, idIndex))
      )
    );

    // Find postcode via deep scan with dereferencing; fallback to URL slug
    const postcode = deepFindPostcode(nodes, idIndex) || getPostcodeFromUrl(item?.url);

    // Create/reuse pill bar
    let bar = element.querySelector(".pill-bar");
    if (!bar && (specialtyNames.length || postcode)) {
      bar = document.createElement("div");
      bar.className = "pill-bar pill-bar-health";
      content.appendChild(bar);
    }

    // Specialty pills
    if (bar && specialtyNames.length) {
      specialtyNames.forEach(name => {
        const pill = document.createElement("span");
        pill.classList.add("pill", "pill-specialty");
        pill.textContent = name;
        pill.setAttribute("aria-label", `Medical specialty: ${name}`);
        bar.appendChild(pill);
      });
    }

    // Postcode pill
    if (bar && postcode && !bar.querySelector(".pill-postcode")) {
      const pill = document.createElement("span");
      pill.className = "pill pill-postcode";
      pill.textContent = `Postcode: ${postcode}`;
      pill.setAttribute("aria-label", `Postcode ${postcode}`);
      bar.appendChild(pill);
    }

    return element;
  }
}

/* ───────────────────────────── helpers ───────────────────────────── */

function buildIdIndex(nodes) {
  const map = new Map();
  for (const n of nodes) {
    const id = n && typeof n === "object" ? n["@id"] : null;
    if (id) map.set(id, n);
  }
  return map;
}

function resolveRef(val, idIndex) {
  // If val is an object like { "@id": "node1" } or a string id, return the indexed node
  if (!val) return null;
  if (typeof val === "string") return idIndex.get(val) || null;
  if (typeof val === "object" && val["@id"] && Object.keys(val).length === 1) {
    return idIndex.get(val["@id"]) || null;
  }
  return null;
}

function extractSpecialties(node, idIndex) {
  if (!node || typeof node !== "object") return [];
  const raw = node.medicalSpecialty ?? resolveRef(node.medicalSpecialty, idIndex);
  if (!raw) return [];

  if (Array.isArray(raw)) {
    return raw
      .map(x => (typeof x === "string" ? x : x?.name ?? resolveRef(x, idIndex)?.name))
      .filter(Boolean);
  }
  if (typeof raw === "string") return [raw];

  const obj = typeof raw === "object" ? raw : resolveRef(raw, idIndex);
  return obj?.name ? [obj.name] : [];
}

function deepFindPostcode(nodes, idIndex) {
  // BFS through all reachable objects/arrays/refs; stop on first AU postcode
  const queue = [];
  const seenObjs = new Set();
  const seenIds = new Set();

  const enqueue = (v) => {
    if (v == null) return;
    if (typeof v === "object") {
      if (seenObjs.has(v)) return;
      seenObjs.add(v);
      queue.push(v);
    } else if (Array.isArray(v)) {
      v.forEach(enqueue);
    } else if (typeof v === "string") {
      // If it's an @id string, deref
      if (v.startsWith("#") || v.startsWith("_:") || v.startsWith("http")) {
        if (!seenIds.has(v)) {
          seenIds.add(v);
          const hit = idIndex.get(v);
          if (hit) enqueue(hit);
        }
      } else {
        // Try to extract a 4-digit code embedded in a string
        const m = v.match(/\b(\d{4})\b/);
        if (isAuPostcode(m?.[1])) return m[1];
      }
    }
  };

  // Seed queue with all nodes
  nodes.forEach(enqueue);

  while (queue.length) {
    const cur = queue.shift();

    // Check explicit postal code properties
    const raw =
      cur.postalCode ?? cur.postCode ?? cur.postcode ?? cur.zipCode ?? cur.zip ?? null;
    if (raw && isAuPostcode(String(raw))) return String(raw).trim();

    // If this is a ref-only object, resolve it
    const ref = resolveRef(cur, idIndex);
    if (ref) {
      enqueue(ref);
      continue;
    }

    // Follow common address/placement slots
    const nexts = [
      cur.address,
      cur.location?.address ?? cur.location,
      cur.geo?.address ?? cur.geo,
      cur.serviceLocation,
      cur.areaServed,
      cur.containedInPlace,
      cur.branchOf,
      cur.parentOrganization,
      cur.department,
      cur.spatialCoverage,
      cur.contentLocation,
    ].filter(Boolean);

    nexts.forEach(enqueue);

    // Also traverse every property (last resort)
    for (const k of Object.keys(cur)) {
      const v = cur[k];
      if (v && typeof v === "object") enqueue(v);
      else if (Array.isArray(v)) v.forEach(enqueue);
      else if (typeof v === "string") {
        const m = v.match(/\b(\d{4})\b/);
        if (isAuPostcode(m?.[1])) return m[1];
        // If property is an @id string, deref
        if ((k === "@id" || k.endsWith("Id")) && idIndex.has(v)) enqueue(idIndex.get(v));
      }
    }
  }

  return null;
}

function getPostcodeFromUrl(url) {
  if (!url) return null;
  // Healthdirect-style slug: "...-2176-nsw/..."
  const m = /-(\d{4})-(nsw|vic|qld|sa|wa|tas|act|nt)\b/i.exec(url);
  return isAuPostcode(m?.[1]) ? m[1] : null;
}

function isAuPostcode(s) {
  return /^\d{4}$/.test(s || "");
}

/**
 * ────────────────────────────
 * Factory
 * ────────────────────────────
 */
export class TypeRendererFactory {
  static registerAll(jsonRenderer) {
    TypeRendererFactory.registerRenderer(RealEstateRenderer, jsonRenderer);
    TypeRendererFactory.registerRenderer(PodcastEpisodeRenderer, jsonRenderer);
    TypeRendererFactory.registerRenderer(HealthCardRenderer, jsonRenderer);
    // RecipeRenderer is registered elsewhere
  }

  static registerRenderer(RendererClass, jsonRenderer) {
    const types =
      typeof RendererClass.supportedTypes === "function"
        ? RendererClass.supportedTypes()
        : RendererClass.supportedTypes;

    const instance = new RendererClass(jsonRenderer);
    const fn = (item) => instance.render(item);

    try {
      types.forEach((t) => jsonRenderer.registerTypeRenderer(t, fn));
    } catch {
      jsonRenderer.registerTypeRenderer(RendererClass, types);
    }
  }
}
 