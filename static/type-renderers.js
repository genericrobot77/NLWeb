// type-renderers.js

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
    // to be implemented by subclasses
    return null;
  }
}

/**
 * Renderer for real estate listings
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

    // attach the explanation/details container
    const detailsDiv = this.jsonRenderer.possiblyAddExplanation(item, contentDiv, true);
    if (!detailsDiv) return element;
    detailsDiv.className = "item-real-estate-details";

    const schema = item.schema_object;
    if (!schema) return element;

    // price
    let priceValue = schema.price;
    if (typeof priceValue === "object") {
      priceValue = priceValue.price || priceValue.value || priceValue;
      if (typeof priceValue === "number") {
        priceValue = Math.round(priceValue / 100000) * 100000;
        priceValue = priceValue.toLocaleString("en-US");
      }
    }

    // address
    const address = schema.address || {};
    const streetAddress   = address.streetAddress   || "";
    const addressLocality = address.addressLocality || "";

    detailsDiv.appendChild(
      this.jsonRenderer.makeAsSpan(`${streetAddress}, ${addressLocality}`)
    );
    detailsDiv.appendChild(document.createElement("br"));

    // beds / baths / sqft
    const beds  = schema.numberOfRooms             || 0;
    const baths = schema.numberOfBathroomsTotal    || 0;
    const sqft  = schema.floorSize?.value          || 0;
    detailsDiv.appendChild(
      this.jsonRenderer.makeAsSpan(`${beds} bedrooms, ${baths} bathrooms, ${sqft} sqft`)
    );
    detailsDiv.appendChild(document.createElement("br"));

    // listed price
    if (priceValue) {
      detailsDiv.appendChild(
        this.jsonRenderer.makeAsSpan(`Listed at ${priceValue}`)
      );
    }

    return element;
  }
}

/**
 * Renderer for podcast episodes
 */
export class PodcastEpisodeRenderer extends TypeRenderer {
  static get supportedTypes() {
    return ["PodcastEpisode"];
  }

  render(item) {
    const element = this.jsonRenderer.createDefaultItemHtml(item);
    const contentDiv = element.querySelector(".item-content");
    if (!contentDiv) return element;

    // ensure explanation is shown
    this.jsonRenderer.possiblyAddExplanation(item, contentDiv, true);
    return element;
  }
}

/**
 * Renderer for MedicalOrganization
 */
/**
 * Renderer for MedicalOrganization
 */
export class MedicalOrganizationRenderer extends TypeRenderer {
  static get supportedTypes() {
    return ["MedicalOrganization"];
  }

  render(item) {
    // create the standard card
    const el = this.jsonRenderer.createDefaultItemHtml(item);
    el.classList.add("item-medical-org");

    // if there's no real image in the schema, drop the placeholder
    if (!item.schema_object?.image && !item.schema_object?.thumbnailUrl) {
      const img = el.querySelector(".item-image");
      if (img) img.remove();
    }

    // nothing else—just return the basic element
    return el;
  }
}


/**
 * Factory to register all renderers
 */
export class TypeRendererFactory {
  /**
   * @param {JsonRenderer} jsonRenderer
   */
  static registerAll(jsonRenderer) {
    TypeRendererFactory.registerRenderer(RealEstateRenderer,    jsonRenderer);
    TypeRendererFactory.registerRenderer(PodcastEpisodeRenderer, jsonRenderer);
    TypeRendererFactory.registerRenderer(MedicalOrganizationRenderer, jsonRenderer);
    // add more here as needed…
  }

  /**
   * @param {typeof TypeRenderer} RendererClass
   * @param {JsonRenderer}      jsonRenderer
   */
  static registerRenderer(RendererClass, jsonRenderer) {
    const renderer = new RendererClass(jsonRenderer);
    RendererClass.supportedTypes.forEach(type => {
      jsonRenderer.registerTypeRenderer(type, item => renderer.render(item));
    });
  }
}
