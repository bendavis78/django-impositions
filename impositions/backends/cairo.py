from __future__ import absolute_import
import re
import cairo
import poppler
import pango
import pangocairo
from impositions.backends import BaseRenderingBackend

if not cairo.HAS_PDF_SURFACE:
    raise SystemExit('cairo was not compiled with PDF support')

class RenderingBackend(BaseRenderingBackend):
    supported_formats = ['pdf', 'png']

    def __init__(self, *args, **kwargs):
        super(RenderingBackend, self).__init__(*args, **kwargs)

        # Get source document
        source_path = self.comp.template.file.path
        self.document = poppler.document_new_from_file('file://{}'.format(source_path), None)
        self.page = self.document.get_page(0)

        # Create destination document
        self.width, self.height = self.page.get_size()
        self.pdf = cairo.PDFSurface(self.output, self.width, self.height)
        self.cr = cairo.Context(self.pdf)

    def render_text_region(self, region):
        x, y = region.template_region.left, region.template_region.top
        self.cr.move_to(x, y)
        pc_context = pangocairo.CairoContext(self.cr)
        pc_context.set_antialias(cairo.ANTIALIAS_SUBPIXEL)
        
        # setup pango layout
        layout = pc_context.create_layout()
        font_desc = '{} {}'.format(region.get_font(), region.get_font_size())
        font = pango.FontDescription(font_desc)
        layout.set_font_description(font)

        # if a width is given, set width and word wrap
        if region.template_region.width:
            layout.set_width(region.template_region.width * pango.SCALE)
            layout.set_wrap(pango.WRAP_WORD)

        content = region.get_content(self.context)
        if not region.template_region.allow_markup:
            content = re.sub(r'<[^>]*?>', '', content)

        # construct surrounding span tag if any style attrs were given
        style = region.template_region.text_style
        if style:
            content = '<span {}>{}</span>'.format(style, content)

        if region.template_region.justify:
            layout.set_justify(True)

        layout.set_markup(content)
        rgb = region.get_fg_color() or (0,0,0)
        self.cr.set_source_rgb(*[int(c) for c in rgb])
        pc_context.update_layout(layout)
        pc_context.show_layout(layout)

    def render_image_region(self, region):
        tpl_region = region.template_region
        img_src = region.get_content(self.context)
        image = cairo.ImageSurface.create_from_png(img_src)

        img_height = image.get_height()
        img_width = image.get_width()
        w = tpl_region.width
        h = tpl_region.height
        x, y = region.template_region.left, region.template_region.top
        self.cr.translate(x, y)
        width_ratio = float(w) / float(img_width)
        height_ratio = float(h) / float(img_height)
        if tpl_region.crop:
            scale_xy = min(height_ratio, width_ratio)
        else:
            scale_xy = max(height_ratio, width_ratio)
        self.cr.scale(scale_xy, scale_xy)
        self.cr.set_source_surface(image)
        self.cr.paint()

    def render(self, fmt):
        self.validate()

        # Render source pdf to destination
        self.cr.save()
        self.page.render(self.cr)
        self.cr.restore()

        for region in self.comp.regions.all():
            self.cr.save()
            if region.template_region.content_type == 'text':
                self.render_text_region(region)
            elif region.template_region.content_type == 'image':
                self.render_image_region(region)
            self.cr.restore()
        
        # Finish
        if fmt == 'pdf':
            self.pdf.show_page()
            return self.output
        elif fmt == 'png':
            self.pdf.write_to_png(self.output)
        else:
            raise ValueError("Format not supported by cairo backend: {}".format(fmt))

        return self.output
