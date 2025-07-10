
from core.config import CONFIG

recipe_sites = ['seriouseats', 'hebbarskitchen', 'latam_recipes',
                'woksoflife', 'cheftariq',  'spruce', 'nytimes']

all_sites = recipe_sites + ["imdb", "npr podcasts", "neurips", "backcountry", "tripadvisor", "DataCommons"]

def siteToItemType(site):
    # Get item type from configuration
    namespace = "http://nlweb.ai/base"
<<<<<<< HEAD
    if isinstance(site, list):
        site = site[0]
    et = "Item"
    if site == "imdb":
        et = "Movie"
    elif site in recipe_sites:
        et = "Recipe"
    elif site == "npr podcasts":
        et = "Thing"
    elif site == "neurips":
        et = "Paper"
    elif site == "backcountry":
        et = "Outdoor Gear"
    elif site == "zillow":
        et = "RealEstate"
    elif site == "datacommons":
        et = "Statistics"
    else:
        et = "Items"
    return f"{{{namespace}}}{et}"
=======
    
    # Try to get from configuration
    try:
        site_config = CONFIG.get_site_config(site.lower())
        if site_config and site_config.item_types:
            # Return the first item type for the site
            return f"{{{namespace}}}{site_config.item_types[0]}"
    except:
        pass
    
    # Default to Item if not found in configuration
    return f"{{{namespace}}}Item"
>>>>>>> 6961914 (Remove old_code and old_static)
    

def itemTypeToSite(item_type):
    # this is used to route queries that this site cannot answer,
    # but some other site can answer. Needs to be generalized.
    sites = []
    for site in all_sites:
        if siteToItemType(site) == item_type:
            sites.append(site)
    return sites
    

def visibleUrlLink(url):
    from urllib.parse import urlparse

def visibleUrl(url):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.netloc.replace('www.', '')

def get_param(query_params, param_name, param_type=str, default_value=None):
    value = query_params.get(param_name, default_value)
    if (value is not None):
        if param_type == str:\
            return value    
        elif param_type == int:\
            return int(value)
        elif param_type == float:
            return float(value) 
        elif param_type == bool:
            if isinstance(value, list):
                return value[0].lower() == "true"
            return value.lower() == "true"
        elif param_type == list:
            if isinstance(value, list):
                return value
            return [item.strip() for item in value.strip('[]').split(',') if item.strip()]
        else:
            raise ValueError(f"Unsupported parameter type: {param_type}")
    return default_value

def log(message):
    print(message)