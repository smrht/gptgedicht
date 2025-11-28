from django import template
from django.utils.safestring import mark_safe
from ads.models import BannerPosition

register = template.Library()


@register.simple_tag
def banner_slot(position_type):
    """
    Render een banner slot voor de gegeven positie.
    Toont actieve banner of placeholder met 'Adverteer hier' link.
    
    Gebruik: {% banner_slot 'sidebar' %}
    """
    try:
        position = BannerPosition.objects.get(position_type=position_type, is_active=True)
    except BannerPosition.DoesNotExist:
        return ''
    
    active_banner = position.get_active_banner()
    
    if active_banner:
        # Toon actieve banner
        html = f'''
        <div class="banner-slot banner-{position_type}">
            <a href="{active_banner.destination_url}" 
               target="_blank" 
               rel="noopener sponsored"
               class="block">
                <img src="{active_banner.image.url}" 
                     alt="{active_banner.alt_text}"
                     width="{position.width}"
                     height="{position.height}"
                     class="rounded-lg shadow-sm hover:shadow-md transition">
            </a>
        </div>
        '''
    else:
        # Toon placeholder
        html = f'''
        <a href="/adverteren/{position.slug}/" 
           class="banner-placeholder block relative group"
           title="Adverteer op deze plek">
            <div class="bg-gradient-to-br from-gray-100 to-gray-200 rounded-lg border-2 border-dashed border-gray-300 
                        flex items-center justify-center group-hover:border-indigo-400 group-hover:from-indigo-50 
                        group-hover:to-purple-50 transition-all duration-300"
                 style="width: {position.width}px; height: {position.height}px; max-width: 100%;">
                <div class="text-center p-4">
                    <div class="text-gray-400 group-hover:text-indigo-500 transition mb-1">
                        <svg class="w-8 h-8 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                  d="M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z"/>
                        </svg>
                    </div>
                    <span class="text-xs text-gray-500 group-hover:text-indigo-600 font-medium transition">
                        Adverteer hier
                    </span>
                    <span class="block text-xs text-gray-400 mt-0.5">{position.width}x{position.height}</span>
                </div>
            </div>
        </a>
        '''
    
    return mark_safe(html)


@register.simple_tag
def banner_slot_inline(position_type):
    """
    Compactere versie voor inline banners (bijv. in content).
    """
    try:
        position = BannerPosition.objects.get(position_type=position_type, is_active=True)
    except BannerPosition.DoesNotExist:
        return ''
    
    active_banner = position.get_active_banner()
    
    if active_banner:
        html = f'''
        <div class="banner-inline my-4">
            <a href="{active_banner.destination_url}" 
               target="_blank" 
               rel="noopener sponsored"
               class="block mx-auto"
               style="max-width: {position.width}px;">
                <img src="{active_banner.image.url}" 
                     alt="{active_banner.alt_text}"
                     class="w-full rounded-lg shadow-sm hover:shadow-md transition">
            </a>
        </div>
        '''
    else:
        html = f'''
        <div class="banner-inline my-4">
            <a href="/adverteren/{position.slug}/" 
               class="block mx-auto group"
               style="max-width: {position.width}px;">
                <div class="bg-gradient-to-r from-gray-100 to-gray-200 rounded-lg border-2 border-dashed border-gray-300
                            py-3 px-4 flex items-center justify-center gap-3 group-hover:border-indigo-400 transition">
                    <svg class="w-5 h-5 text-gray-400 group-hover:text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                              d="M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z"/>
                    </svg>
                    <span class="text-sm text-gray-500 group-hover:text-indigo-600 font-medium">
                        Adverteer hier • Vanaf €{{ position.price_month }}/maand
                    </span>
                </div>
            </a>
        </div>
        '''
    
    return mark_safe(html)
