/**
 * Type-specific renderers for JSON objects
 */

/**
 * Base class for type-specific renderers
 */
export class TypeRenderer {
  /**
   * Creates a new TypeRenderer
   * 
   * @param {JsonRenderer} jsonRenderer - The parent JSON renderer
   */
  constructor(jsonRenderer) {
    this.jsonRenderer = jsonRenderer;
  }
  
  /**
   * Renders an item
   * 
   * @param {Object} item - The item to render
   * @returns {HTMLElement} - The rendered HTML
   */
  render(item) {
    // To be implemented by subclasses
    return null;
  }
}

/**
 * Renderer for real estate listings
 */
export class RealEstateRenderer extends TypeRenderer {
  /**
   * Types that this renderer can handle
   * 
   * @returns {Array<string>} - The types this renderer can handle
   */
  static get supportedTypes() {
    return [
      "SingleFamilyResidence", 
      "Apartment", 
      "Townhouse", 
      "House", 
      "Condominium", 
      "RealEstateListing"
    ];
  }
  
  /**
   * Renders a real estate item
   * 
   * @param {Object} item - The item to render
   * @returns {HTMLElement} - The rendered HTML
   */
  render(item) {
    // Use the default item HTML as a base
    const element = this.jsonRenderer.createDefaultItemHtml(item);
    
    // Find the content div
    const contentDiv = element.querySelector('.item-content');
    if (!contentDiv) return element;
    
    // Add real estate specific details
    const detailsDiv = this.jsonRenderer.possiblyAddExplanation(item, contentDiv, true);
    if (!detailsDiv) return element;
    
    detailsDiv.className = 'item-real-estate-details';
    
    const schema = item.schema_object;
    if (!schema) return element;
    
    const price = schema.price;
    const address = schema.address || {};
    const numBedrooms = schema.numberOfRooms;
    const numBathrooms = schema.numberOfBathroomsTotal;
    const sqft = schema.floorSize?.value;
    
    let priceValue = price;
    if (typeof price === 'object') {
      priceValue = price.price || price.value || price;
      if (typeof priceValue === 'number') {
        priceValue = Math.round(priceValue / 100000) * 100000;
        priceValue = priceValue.toLocaleString('en-US');
      }
    }

    const streetAddress = address.streetAddress || '';
    const addressLocality = address.addressLocality || '';
    detailsDiv.appendChild(this.jsonRenderer.makeAsSpan(`${streetAddress}, ${addressLocality}`));
    detailsDiv.appendChild(document.createElement('br'));
    
    const bedroomsText = numBedrooms || '0';
    const bathroomsText = numBathrooms || '0';
    const sqftText = sqft || '0';
    detailsDiv.appendChild(this.jsonRenderer.makeAsSpan(`${bedroomsText} bedrooms, ${bathroomsText} bathrooms, ${sqftText} sqft`));
    detailsDiv.appendChild(document.createElement('br'));
    
    if (priceValue) {
      detailsDiv.appendChild(this.jsonRenderer.makeAsSpan(`Listed at ${priceValue}`));
    }
    
    return element;
  }
}

/**
 * Renderer for podcast episodes
 */
export class PodcastEpisodeRenderer extends TypeRenderer {
  /**
   * Types that this renderer can handle
   * 
   * @returns {Array<string>} - The types this renderer can handle
   */
  static get supportedTypes() {
    return ["PodcastEpisode"];
  }
  
  /**
   * Renders a podcast episode item
   * 
   * @param {Object} item - The item to render
   * @returns {HTMLElement} - The rendered HTML
   */
  render(item) {
    // Use the default item HTML as a base
    const element = this.jsonRenderer.createDefaultItemHtml(item);
    
    // Find the content div
    const contentDiv = element.querySelector('.item-content');
    if (!contentDiv) return element;
    
    // Add podcast specific details - in this case just ensure explanation is shown
    this.jsonRenderer.possiblyAddExplanation(item, contentDiv, true);
    
    return element;
  }
}

/**
 * Renderer for medical specialty pills
 * Applies to Place and MedicalOrganization types
 */

export class SpecialtyPillRenderer extends TypeRenderer {
  static get supportedTypes() {
    return ["Place", "MedicalOrganization"];
  }

  render(item) {
    // Build base card
    const element = this.jsonRenderer.createDefaultItemHtml(item);
    const contentDiv = element.querySelector(".item-content");
    if (!contentDiv) return element;

    // Normalize schema nodes (array or single)
    const nodes = Array.isArray(item.schema_object)
      ? item.schema_object.filter(Boolean)
      : item.schema_object
        ? [item.schema_object]
        : [];

    // Extract medical specialty names from all nodes, tolerate multiple shapes
    const names = Array.from(new Set(
      nodes.flatMap(n => {
        const raw = n?.medicalSpecialty;
        if (!raw) return [];
        // medicalSpecialty can be:
        //  - [{ "@type": "MedicalSpecialty", "name": "X" }, ...]
        //  - "X"
        //  - ["X","Y"]
        //  - { "@type": "MedicalSpecialty", "name": "X" }
        if (Array.isArray(raw)) {
          return raw.map(x => (typeof x === "string" ? x : x?.name)).filter(Boolean);
        }
        if (typeof raw === "string") return [raw];
        if (typeof raw === "object" && raw !== null) return raw.name ? [raw.name] : [];
        return [];
      })
    ));

    if (names.length === 0) return element;

    // Create pill bar
    const bar = document.createElement("div");
    bar.classList.add("pill-bar", "pill-bar-specialties");

    names.forEach(name => {
      const pill = document.createElement("span");
      pill.classList.add("pill", "pill-specialty");
      pill.textContent = name;
      pill.setAttribute("aria-label", `Medical specialty: ${name}`);
      bar.appendChild(pill);
    });

    // Insert below explanation/description if present, else at top of content
    const anchor =
      element.querySelector(".item-explanation") ||
      element.querySelector(".item-description");
    if (anchor) anchor.after(bar);
    else contentDiv.prepend(bar);

    return element;
  }
}


/**
 * Factory for creating type renderers
 */
export class TypeRendererFactory {
  /**
   * Registers all type renderers with a JSON renderer
   */
  static registerAll(jsonRenderer) {
    TypeRendererFactory.registerRenderer(RealEstateRenderer, jsonRenderer);
    TypeRendererFactory.registerRenderer(PodcastEpisodeRenderer, jsonRenderer);
    TypeRendererFactory.registerRenderer(SpecialtyPillRenderer, jsonRenderer);
    // RecipeRenderer will be registered separately
    // Add more renderers here as needed
  }
  
  static registerRenderer(RendererClass, jsonRenderer) {
  // Resolve supported types whether defined as a getter or a method
  const types = typeof RendererClass.supportedTypes === "function"
    ? RendererClass.supportedTypes()
    : RendererClass.supportedTypes;

  // Instance-based renderer function
  const instance = new RendererClass(jsonRenderer);
  const fn = (item) => instance.render(item);

  // Try “per-type callback” signature first; fall back to “class + types”
  try {
    // If method supports (type, fn), this will succeed for the first type
    // We'll register all types this way.
    types.forEach(t => jsonRenderer.registerTypeRenderer(t, fn));
  } catch {
    // Old API: (RendererClass, typesArray)
    jsonRenderer.registerTypeRenderer(RendererClass, types);
  }
}

}
