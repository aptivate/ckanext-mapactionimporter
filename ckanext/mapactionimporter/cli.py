import click

from ckanext.mapactionimporter.plugin import (
    create_product_themes
)

def get_commands():

    @click.group()
    def mapactionimporter():
        """Generates mapactionimporter command"""
        pass
    
    @mapactionimporter.command(name='create_product_themes')
    def themes():
        create_product_themes()
    
    return [mapactionimporter]
