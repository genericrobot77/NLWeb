/**
 * Type-specific renderers for JSON objects
 */

/**
 * Base class for type-specific renderers
 */
export class TypeRenderer {
  /**
   * @param {JsonRenderer} jsonRenderer - The parent JSON renderer
   */
  constructor(jsonRenderer) {
    this.jsonRenderer = jsonRenderer;
  }

  /**
   * Renders an item
   * @param {Object} item - The item to render
   * @returns {HTMLElement|null}
   */
  render(item) {
    return null; // to be implemented by subclasses
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
    const contentDiv = element.querySelector('.item-content');
    if (!contentDiv) return element;

    const detailsDiv = this.jsonRenderer.possiblyAddExplanation(item, contentDiv, true);
    if (!detailsDiv) return element;
    detailsDiv.classList.add('item-real-estate-details');

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

    const street = address.streetAddress || '';
    const locality = address.addressLocality || '';
    detailsDiv.appendChild(this.jsonRenderer.makeAsSpan(`${street}, ${locality}`));
    detailsDiv.appendChild(document.createElement('br'));

    detailsDiv.appendChild(
      this.jsonRenderer.makeAsSpan(
        `${numBedrooms || 0} bedrooms, ${numBathrooms || 0} bathrooms, ${sqft || 0} sqft`
      )
    );
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
  static get supportedTypes() {
    return ["PodcastEpisode"];
  }

  render(item) {
    const element = this.jsonRenderer.createDefaultItemHtml(item);
    const contentDiv = element.querySelector('.item-content');
    if (!contentDiv) return element;
    this.jsonRenderer.possiblyAddExplanation(item, contentDiv, true);
    return element;
  }
}

/**
 * Renderer for MedicalOrganization, adding postcode display
 */
export class MedicalOrganizationRenderer extends TypeRenderer {
  static get supportedTypes() {
    return ["MedicalOrganization"];
  }

  render(item) {
    // Base card
    const element = this.jsonRenderer.createDefaultItemHtml(item);
    const contentDiv = element.querySelector('.item-content');
    if (!contentDiv) return element;

    // Extract schema node
    const nodes = Array.isArray(item.schema_object)
      ? item.schema_object
      : [item.schema_object].filter(Boolean);
    const schema = nodes[0] || {};

    // Read postcode
    const postcode = schema.location?.address?.postalCode || schema.address?.postalCode;
    if (postcode) {
      // Append postcode
      const span = this.jsonRenderer.makeAsSpan(`Postcode: ${postcode}`);
      span.classList.add('item-postcode');
      contentDiv.appendChild(document.createElement('br'));
      contentDiv.appendChild(span);
    }

    return element;
  }
}

/**
 * Factory for registering all type renderers
 */
export class TypeRendererFactory {
  static registerAll(jsonRenderer) {
    TypeRendererFactory.registerRenderer(RealEstateRenderer, jsonRenderer);
    TypeRendererFactory.registerRenderer(PodcastEpisodeRenderer, jsonRenderer);
    TypeRendererFactory.registerRenderer(MedicalOrganizationRenderer, jsonRenderer);
  }

  static registerRenderer(RendererClass, jsonRenderer) {
    const renderer = new RendererClass(jsonRenderer);
    RendererClass.supportedTypes.forEach(type => {
      jsonRenderer.registerTypeRenderer(type, item => renderer.render(item));
    });
  }
}
