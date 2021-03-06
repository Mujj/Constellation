from __future__ import division

import os, codecs, base64, tempfile, urllib, gzip, cStringIO

import numpy as np

try:
    from hashlib import md5
except ImportError:
    from md5 import md5 #Deprecated in 2.5

from matplotlib import verbose, __version__, rcParams
from matplotlib.backend_bases import RendererBase, GraphicsContextBase,\
     FigureManagerBase, FigureCanvasBase
from matplotlib.backends.backend_mixed import MixedModeRenderer
from matplotlib.cbook import is_string_like, is_writable_file_like, maxdict
from matplotlib.colors import rgb2hex
from matplotlib.figure import Figure
from matplotlib.font_manager import findfont, FontProperties
from matplotlib.ft2font import FT2Font, KERNING_DEFAULT, LOAD_NO_HINTING
from matplotlib.mathtext import MathTextParser
from matplotlib.path import Path
from matplotlib.transforms import Affine2D
from matplotlib import _png

from xml.sax.saxutils import escape as escape_xml_text

backend_version = __version__

def new_figure_manager(num, *args, **kwargs):
    FigureClass = kwargs.pop('FigureClass', Figure)
    thisFig = FigureClass(*args, **kwargs)
    canvas  = FigureCanvasSVG(thisFig)
    manager = FigureManagerSVG(canvas, num)
    return manager


_capstyle_d = {'projecting' : 'square', 'butt' : 'butt', 'round': 'round',}
class RendererSVG(RendererBase):
    FONT_SCALE = 100.0
    fontd = maxdict(50)

    def __init__(self, width, height, svgwriter, basename=None):
        self.width=width
        self.height=height
        self._svgwriter = svgwriter

        self._groupd = {}
        if not rcParams['svg.image_inline']:
            assert basename is not None
            self.basename = basename
            self._imaged = {}
        self._clipd = {}
        self._char_defs = {}
        self._markers = {}
        self._path_collection_id = 0
        self._imaged = {}
        self._hatchd = {}
        self._n_gradients = 0
        self.mathtext_parser = MathTextParser('SVG')

        RendererBase.__init__(self)
        self._glyph_map = dict()

        svgwriter.write(svgProlog%(width,height,width,height))

    def _draw_svg_element(self, element, details, gc, rgbFace):
        clipid = self._get_gc_clip_svg(gc)
        if clipid is None:
            clippath = ''
        else:
            clippath = 'clip-path="url(#%s)"' % clipid

        if gc.get_url() is not None:
            self._svgwriter.write('<a xlink:href="%s">' % gc.get_url())
        style = self._get_style(gc, rgbFace)
        self._svgwriter.write ('<%s style="%s" %s %s/>\n' % (
                element, style, clippath, details))
        if gc.get_url() is not None:
            self._svgwriter.write('</a>')

    def _get_font(self, prop):
        key = hash(prop)
        font = self.fontd.get(key)
        if font is None:
            fname = findfont(prop)
            font = self.fontd.get(fname)
            if font is None:
                font = FT2Font(str(fname))
                self.fontd[fname] = font
            self.fontd[key] = font
        font.clear()
        size = prop.get_size_in_points()
        font.set_size(size, 72.0)
        return font

    def _get_hatch(self, gc, rgbFace):
        """
        Create a new hatch pattern
        """
        HATCH_SIZE = 72
        dictkey = (gc.get_hatch(), rgbFace, gc.get_rgb())
        id = self._hatchd.get(dictkey)
        if id is None:
            id = 'h%s' % md5(str(dictkey)).hexdigest()
            self._svgwriter.write('<defs>\n  <pattern id="%s" ' % id)
            self._svgwriter.write('patternUnits="userSpaceOnUse" x="0" y="0" ')
            self._svgwriter.write(' width="%d" height="%d" >\n' % (HATCH_SIZE, HATCH_SIZE))
            path_data = self._convert_path(
                gc.get_hatch_path(),
                Affine2D().scale(HATCH_SIZE).scale(1.0, -1.0).translate(0, HATCH_SIZE),
                simplify=False)
            if rgbFace is None:
                fill = 'none'
            else:
                fill = rgb2hex(rgbFace)
            self._svgwriter.write(
                '<rect x="0" y="0" width="%d" height="%d" fill="%s"/>' %
                (HATCH_SIZE+1, HATCH_SIZE+1, fill))
            path = '<path d="%s" fill="%s" stroke="%s" stroke-width="1.0"/>' % (
                path_data, rgb2hex(gc.get_rgb()), rgb2hex(gc.get_rgb()))
            self._svgwriter.write(path)
            self._svgwriter.write('\n  </pattern>\n</defs>')
            self._hatchd[dictkey] = id
        return id

    def _get_style(self, gc, rgbFace):
        """
        return the style string.
        style is generated from the GraphicsContext, rgbFace and clippath
        """
        if gc.get_hatch() is not None:
            fill = "url(#%s)" % self._get_hatch(gc, rgbFace)
        else:
            if rgbFace is None:
                fill = 'none'
            else:
                fill = rgb2hex(rgbFace)

        offset, seq = gc.get_dashes()
        if seq is None:
            dashes = ''
        else:
            dashes = 'stroke-dasharray: %s; stroke-dashoffset: %f;' % (
                ','.join(['%f'%val for val in seq]), offset)

        linewidth = gc.get_linewidth()
        if linewidth:
            return 'fill: %s; stroke: %s; stroke-width: %f; ' \
                'stroke-linejoin: %s; stroke-linecap: %s; %s opacity: %f' % (
                         fill,
                         rgb2hex(gc.get_rgb()),
                         linewidth,
                         gc.get_joinstyle(),
                         _capstyle_d[gc.get_capstyle()],
                         dashes,
                         gc.get_alpha(),
                )
        else:
            return 'fill: %s; opacity: %f' % (\
                         fill,
                         gc.get_alpha(),
                )

    def _get_gc_clip_svg(self, gc):
        cliprect = gc.get_clip_rectangle()
        clippath, clippath_trans = gc.get_clip_path()
        if clippath is not None:
            clippath_trans = self._make_flip_transform(clippath_trans)
            path_data = self._convert_path(clippath, clippath_trans, simplify=False)
            path = '<path d="%s"/>' % path_data
        elif cliprect is not None:
            x, y, w, h = cliprect.bounds
            y = self.height-(y+h)
            path = '<rect x="%(x)f" y="%(y)f" width="%(w)f" height="%(h)f"/>' % locals()
        else:
            return None

        id = self._clipd.get(path)
        if id is None:
            id = 'p%s' % md5(path).hexdigest()
            self._svgwriter.write('<defs>\n  <clipPath id="%s">\n' % id)
            self._svgwriter.write(path)
            self._svgwriter.write('\n  </clipPath>\n</defs>')
            self._clipd[path] = id
        return id

    def open_group(self, s, gid=None):
        """
        Open a grouping element with label *s*. If *gid* is given, use
        *gid* as the id of the group.
        """
        if gid:
            self._svgwriter.write('<g id="%s">\n' % (gid))
        else:
            self._groupd[s] = self._groupd.get(s,0) + 1
            self._svgwriter.write('<g id="%s%d">\n' % (s, self._groupd[s]))

    def close_group(self, s):
        self._svgwriter.write('</g>\n')

    def option_image_nocomposite(self):
        """
        if svg.image_noscale is True, compositing multiple images into one is prohibited
        """
        return rcParams['svg.image_noscale']

    _path_commands = {
        Path.MOVETO: 'M%f %f',
        Path.LINETO: 'L%f %f',
        Path.CURVE3: 'Q%f %f %f %f',
        Path.CURVE4: 'C%f %f %f %f %f %f'
        }

    def _make_flip_transform(self, transform):
        return (transform +
                Affine2D()
                .scale(1.0, -1.0)
                .translate(0.0, self.height))

    def _convert_path(self, path, transform, clip=False, simplify=None):
        path_data = []
        appender = path_data.append
        path_commands = self._path_commands
        currpos = 0
        if clip:
            clip = (0.0, 0.0, self.width, self.height)
        else:
            clip = None
        for points, code in path.iter_segments(transform, clip=clip,
                                               simplify=simplify):
            if code == Path.CLOSEPOLY:
                segment = 'z'
            else:
                segment = path_commands[code] % tuple(points)

            if currpos + len(segment) > 75:
                appender("\n")
                currpos = 0
            appender(segment)
            currpos += len(segment)
        return ''.join(path_data)

    def draw_path(self, gc, path, transform, rgbFace=None):
        trans_and_flip = self._make_flip_transform(transform)
        clip = (rgbFace is None and gc.get_hatch_path() is None)
        simplify = path.should_simplify and clip
        path_data = self._convert_path(
            path, trans_and_flip, clip=clip, simplify=simplify)
        self._draw_svg_element('path', 'd="%s"' % path_data, gc, rgbFace)

    def draw_markers(self, gc, marker_path, marker_trans, path, trans, rgbFace=None):
        write = self._svgwriter.write

        key = self._convert_path(marker_path,
                                 marker_trans + Affine2D().scale(1.0, -1.0),
                                 simplify=False)
        name = self._markers.get(key)
        if name is None:
            name = 'm%s' % md5(key).hexdigest()
            write('<defs><path id="%s" d="%s"/></defs>\n' % (name, key))
            self._markers[key] = name

        clipid = self._get_gc_clip_svg(gc)
        if clipid is None:
            clippath = ''
        else:
            clippath = 'clip-path="url(#%s)"' % clipid

        write('<g %s>' % clippath)
        trans_and_flip = self._make_flip_transform(trans)
        for vertices, code in path.iter_segments(trans_and_flip, simplify=False):
            if len(vertices):
                x, y = vertices[-2:]
                details = 'xlink:href="#%s" x="%f" y="%f"' % (name, x, y)
                style = self._get_style(gc, rgbFace)
                self._svgwriter.write ('<use style="%s" %s/>\n' % (style, details))
        write('</g>')

    def draw_path_collection(self, gc, master_transform, paths, all_transforms,
                             offsets, offsetTrans, facecolors, edgecolors,
                             linewidths, linestyles, antialiaseds, urls):
        write = self._svgwriter.write

        path_codes = []
        write('<defs>\n')
        for i, (path, transform) in enumerate(self._iter_collection_raw_paths(
            master_transform, paths, all_transforms)):
            transform = Affine2D(transform.get_matrix()).scale(1.0, -1.0)
            d = self._convert_path(path, transform, simplify=False)
            name = 'coll%x_%x_%s' % (self._path_collection_id, i,
                                     md5(d).hexdigest())
            write('<path id="%s" d="%s"/>\n' % (name, d))
            path_codes.append(name)
        write('</defs>\n')

        for xo, yo, path_id, gc0, rgbFace in self._iter_collection(
            gc, path_codes, offsets, offsetTrans, facecolors, edgecolors,
            linewidths, linestyles, antialiaseds, urls):
            clipid = self._get_gc_clip_svg(gc0)
            url = gc0.get_url()
            if url is not None:
                self._svgwriter.write('<a xlink:href="%s">' % url)
            if clipid is not None:
                write('<g clip-path="url(#%s)">' % clipid)
            details = 'xlink:href="#%s" x="%f" y="%f"' % (path_id, xo, self.height - yo)
            style = self._get_style(gc0, rgbFace)
            self._svgwriter.write ('<use style="%s" %s/>\n' % (style, details))
            if clipid is not None:
                write('</g>')
            if url is not None:
                self._svgwriter.write('</a>')

        self._path_collection_id += 1

    def draw_gouraud_triangle(self, gc, points, colors, trans):
        # This uses a method described here:
        #
        #   http://www.svgopen.org/2005/papers/Converting3DFaceToSVG/index.html
        #
        # that uses three overlapping linear gradients to simulate a
        # Gouraud triangle.  Each gradient goes from fully opaque in
        # one corner to fully transparent along the opposite edge.
        # The line between the stop points is perpendicular to the
        # opposite edge.  Underlying these three gradients is a solid
        # triangle whose color is the average of all three points.

        avg_color = np.sum(colors[:, :], axis=0) / 3.0
        # Just skip fully-transparent triangles
        if avg_color[-1] == 0.0:
            return

        trans_and_flip = self._make_flip_transform(trans)
        tpoints = trans_and_flip.transform(points)
        write = self._svgwriter.write

        write('<defs>')
        for i in range(3):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % 3]
            x3, y3 = points[(i + 2) % 3]
            c = colors[i][:]

            if x2 == x3:
                xb = x2
                yb = y1
            elif y2 == y3:
                xb = x1
                yb = y2
            else:
                m1 = (y2 - y3) / (x2 - x3)
                b1 = y2 - (m1 * x2)
                m2 = -(1.0 / m1)
                b2 = y1 - (m2 * x1)
                xb = (-b1 + b2) / (m1 - m2)
                yb = m2 * xb + b2

            write('<linearGradient id="GR%x_%d" x1="%f" y1="%f" x2="%f" y2="%f" gradientUnits="userSpaceOnUse">' %
                  (self._n_gradients, i, x1, y1, xb, yb))
            write('<stop offset="0" style="stop-color:%s;stop-opacity:%f"/>' % (rgb2hex(c), c[-1]))
            write('<stop offset="1" style="stop-color:%s;stop-opacity:0"/>' % rgb2hex(c))
            write('</linearGradient>')

        # Define the triangle itself as a "def" since we use it 4 times
        write('<polygon id="GT%x" points="%f %f %f %f %f %f"/>' %
              (self._n_gradients, x1, y1, x2, y2, x3, y3))
        write('</defs>\n')

        avg_color = np.sum(colors[:, :], axis=0) / 3.0
        write('<use xlink:href="#GT%x" fill="%s" fill-opacity="%f"/>\n' %
              (self._n_gradients, rgb2hex(avg_color), avg_color[-1]))
        for i in range(3):
            write('<use xlink:href="#GT%x" fill="url(#GR%x_%d)" fill-opacity="1" filter="url(#colorAdd)"/>\n' %
                  (self._n_gradients, self._n_gradients, i))

        self._n_gradients += 1

    def draw_gouraud_triangles(self, gc, triangles_array, colors_array,
                               transform):
        write = self._svgwriter.write

        clipid = self._get_gc_clip_svg(gc)
        if clipid is None:
            clippath = ''
        else:
            clippath = 'clip-path="url(#%s)"' % clipid

        write('<g %s>\n' % clippath)

        transform = transform.frozen()
        for tri, col in zip(triangles_array, colors_array):
            self.draw_gouraud_triangle(gc, tri, col, transform)

        write('</g>\n')

    def draw_image(self, gc, x, y, im):
        clipid = self._get_gc_clip_svg(gc)
        if clipid is None:
            clippath = ''
        else:
            clippath = 'clip-path="url(#%s)"' % clipid

        trans = [1,0,0,1,0,0]
        transstr = ''
        if rcParams['svg.image_noscale']:
            trans = list(im.get_matrix())
            trans[5] = -trans[5]
            transstr = 'transform="matrix(%f %f %f %f %f %f)" ' % tuple(trans)
            assert trans[1] == 0
            assert trans[2] == 0
            numrows,numcols = im.get_size()
            im.reset_matrix()
            im.set_interpolation(0)
            im.resize(numcols, numrows)

        h,w = im.get_size_out()

        url = getattr(im, '_url', None)
        if url is not None:
            self._svgwriter.write('<a xlink:href="%s">' % url)
        self._svgwriter.write (
            '<image x="%f" y="%f" width="%f" height="%f" '
            '%s %s xlink:href="' % (
                x/trans[0], (self.height-y)/trans[3]-h, w, h,
                transstr, clippath)
            )

        if rcParams['svg.image_inline']:
            self._svgwriter.write("data:image/png;base64,\n")
            stringio = cStringIO.StringIO()
            im.flipud_out()
            rows, cols, buffer = im.as_rgba_str()
            _png.write_png(buffer, cols, rows, stringio)
            im.flipud_out()
            self._svgwriter.write(base64.encodestring(stringio.getvalue()))
        else:
            self._imaged[self.basename] = self._imaged.get(self.basename,0) + 1
            filename = '%s.image%d.png'%(self.basename, self._imaged[self.basename])
            verbose.report( 'Writing image file for inclusion: %s' % filename)
            im.flipud_out()
            rows, cols, buffer = im.as_rgba_str()
            _png.write_png(buffer, cols, rows, filename)
            im.flipud_out()
            self._svgwriter.write(filename)

        self._svgwriter.write('"/>\n')
        if url is not None:
            self._svgwriter.write('</a>')

    def _adjust_char_id(self, char_id):
        return char_id.replace("%20","_")

    def draw_text_as_path(self, gc, x, y, s, prop, angle, ismath):
        """
        draw the text by converting them to paths using textpath module.

        *prop*
          font property

        *s*
          text to be converted

        *usetex*
          If True, use matplotlib usetex mode.

        *ismath*
          If True, use mathtext parser. If "TeX", use *usetex* mode.


        """
        # this method works for normal text, mathtext and usetex mode.
        # But currently only utilized by draw_tex method.

        glyph_map=self._glyph_map

        text2path = self._text2path
        color = rgb2hex(gc.get_rgb())
        fontsize = prop.get_size_in_points()

        write = self._svgwriter.write

        if ismath == False:
            font = text2path._get_font(prop)
            _glyphs = text2path.get_glyphs_with_font(font, s, glyph_map=glyph_map,
                                                     return_new_glyphs_only=True)
            glyph_info, glyph_map_new, rects = _glyphs

            _flip = Affine2D().scale(1.0, -1.0)

            if glyph_map_new:
                write('<defs>\n')
                for char_id, glyph_path in glyph_map_new.iteritems():
                    path = Path(*glyph_path)
                    path_data = self._convert_path(path, _flip, simplify=False)
                    path_element = '<path id="%s" d="%s"/>\n' % (char_id, ''.join(path_data))
                    write(path_element)
                write('</defs>\n')

                glyph_map.update(glyph_map_new)

            svg = []
            clipid = self._get_gc_clip_svg(gc)
            if clipid is not None:
                svg.append('<g clip-path="url(#%s)">\n' % clipid)

            svg.append('<g style="fill: %s; opacity: %f" transform="' % (color, gc.get_alpha()))
            if angle != 0:
                svg.append('translate(%f,%f)rotate(%1.1f)' % (x,y,-angle))
            elif x != 0 or y != 0:
                svg.append('translate(%f,%f)' % (x, y))
            svg.append('scale(%f)">\n' % (fontsize / text2path.FONT_SCALE))

            for glyph_id, xposition, yposition, scale in glyph_info:
                svg.append('<use xlink:href="#%s"' % glyph_id)
                svg.append(' x="%f" y="%f"' % (xposition, yposition))
                #(currx * (self.FONT_SCALE / fontsize)))
                svg.append('/>\n')

            svg.append('</g>\n')
            if clipid is not None:
                svg.append('</g>\n')
            svg = ''.join(svg)



        else:
            if ismath == "TeX":
                _glyphs = text2path.get_glyphs_tex(prop, s, glyph_map=glyph_map)
            else:
                _glyphs = text2path.get_glyphs_mathtext(prop, s, glyph_map=glyph_map)

            glyph_info, glyph_map_new, rects = _glyphs

            # we store the character glyphs w/o flipping. Instead, the
            # coordinate will be flipped when this characters are
            # used.
            if glyph_map_new:
                write('<defs>\n')
                for char_id, glyph_path in glyph_map_new.iteritems():
                    char_id = self._adjust_char_id(char_id)
                    path = Path(*glyph_path)
                    path_data = self._convert_path(path, None, simplify=False) #_flip)
                    path_element = '<path id="%s" d="%s"/>\n' % (char_id, ''.join(path_data))
                    write(path_element)
                write('</defs>\n')

                glyph_map.update(glyph_map_new)

            svg = []
            clipid = self._get_gc_clip_svg(gc)
            if clipid is not None:
                svg.append('<g clip-path="url(#%s)">\n' % clipid)

            svg.append('<g style="fill: %s; opacity: %f" transform="' % (color, gc.get_alpha()))
            if angle != 0:
                svg.append('translate(%f,%f)rotate(%1.1f)' % (x,y,-angle))
            elif x != 0 or y != 0:
                svg.append('translate(%f,%f)' % (x, y))
            svg.append('scale(%f,-%f)">\n' % (fontsize / text2path.FONT_SCALE,
                                              fontsize / text2path.FONT_SCALE))

            for char_id, xposition, yposition, scale in glyph_info:
                char_id = self._adjust_char_id(char_id)
                svg.append('<use xlink:href="#%s"' % char_id)
                svg.append(' x="%f" y="%f" transform="scale(%f)"' % (xposition/scale,
                                                                      yposition/scale,
                                                                      scale))
                svg.append('/>\n')


            for verts, codes in rects:
                path = Path(verts, codes)
                path_data = self._convert_path(path, None, simplify=False)
                path_element = '<path d="%s"/>\n' % (''.join(path_data))
                svg.append(path_element)


            svg.append('</g><!-- style -->\n')
            if clipid is not None:
                svg.append('</g><!-- clipid -->\n')
            svg = ''.join(svg)

        write(svg)


    def draw_tex(self, gc, x, y, s, prop, angle):
        self.draw_text_as_path(gc, x, y, s, prop, angle, ismath="TeX")

    def draw_text(self, gc, x, y, s, prop, angle, ismath):

        if ismath:
            self._draw_mathtext(gc, x, y, s, prop, angle)
            return

        font = self._get_font(prop)
        font.set_text(s, 0.0, flags=LOAD_NO_HINTING)
        y -= font.get_descent() / 64.0

        fontsize = prop.get_size_in_points()
        color = rgb2hex(gc.get_rgb())
        write = self._svgwriter.write

        if rcParams['svg.embed_char_paths']:
            new_chars = []
            for c in s:
                path = self._add_char_def(prop, c)
                if path is not None:
                    new_chars.append(path)
            if len(new_chars):
                write('<defs>\n')
                for path in new_chars:
                    write(path)
                write('</defs>\n')

            svg = []
            clipid = self._get_gc_clip_svg(gc)
            if clipid is not None:
                svg.append('<g clip-path="url(#%s)">\n' % clipid)

            svg.append('<g style="fill: %s; opacity: %f" transform="' % (color, gc.get_alpha()))
            if angle != 0:
                svg.append('translate(%f,%f)rotate(%1.1f)' % (x,y,-angle))
            elif x != 0 or y != 0:
                svg.append('translate(%f,%f)' % (x, y))
            svg.append('scale(%f)">\n' % (fontsize / self.FONT_SCALE))

            cmap = font.get_charmap()
            lastgind = None
            currx = 0
            for c in s:
                charnum = self._get_char_def_id(prop, c)
                ccode = ord(c)
                gind = cmap.get(ccode)
                if gind is None:
                    ccode = ord('?')
                    gind = 0
                glyph = font.load_char(ccode, flags=LOAD_NO_HINTING)

                if lastgind is not None:
                    kern = font.get_kerning(lastgind, gind, KERNING_DEFAULT)
                else:
                    kern = 0
                currx += (kern / 64.0) / (self.FONT_SCALE / fontsize)

                svg.append('<use xlink:href="#%s"' % charnum)
                if currx != 0:
                    svg.append(' x="%f"' %
                               (currx * (self.FONT_SCALE / fontsize)))
                svg.append('/>\n')

                currx += (glyph.linearHoriAdvance / 65536.0) / (self.FONT_SCALE / fontsize)
                lastgind = gind
            svg.append('</g>\n')
            if clipid is not None:
                svg.append('</g>\n')
            svg = ''.join(svg)
        else:
            thetext = escape_xml_text(s)
            fontfamily = font.family_name
            fontstyle = prop.get_style()

            style = ('font-size: %f; font-family: %s; font-style: %s; fill: %s; opacity: %f' %
                     (fontsize, fontfamily,fontstyle, color, gc.get_alpha()))
            if angle!=0:
                transform = 'transform="translate(%f,%f) rotate(%1.1f) translate(%f,%f)"' % (x,y,-angle,-x,-y)
                # Inkscape doesn't support rotate(angle x y)
            else:
                transform = ''

            svg = """\
<text style="%(style)s" x="%(x)f" y="%(y)f" %(transform)s>%(thetext)s</text>
""" % locals()
        write(svg)

    def _add_char_def(self, prop, char):
        if isinstance(prop, FontProperties):
            newprop = prop.copy()
            font = self._get_font(newprop)
        else:
            font = prop
        font.set_size(self.FONT_SCALE, 72)
        ps_name = font.get_sfnt()[(1,0,0,6)]
        char_id = urllib.quote('%s-%d' % (ps_name, ord(char)))
        char_num = self._char_defs.get(char_id, None)
        if char_num is not None:
            return None

        path_data = []
        glyph = font.load_char(ord(char), flags=LOAD_NO_HINTING)
        currx, curry = 0.0, 0.0
        for step in glyph.path:
            if step[0] == 0:   # MOVE_TO
                path_data.append("M%f %f" %
                                 (step[1], -step[2]))
            elif step[0] == 1: # LINE_TO
                path_data.append("l%f %f" %
                                 (step[1] - currx, -step[2] - curry))
            elif step[0] == 2: # CURVE3
                path_data.append("q%f %f %f %f" %
                                 (step[1] - currx, -step[2] - curry,
                                  step[3] - currx, -step[4] - curry))
            elif step[0] == 3: # CURVE4
                path_data.append("c%f %f %f %f %f %f" %
                                 (step[1] - currx, -step[2] - curry,
                                  step[3] - currx, -step[4] - curry,
                                  step[5] - currx, -step[6] - curry))
            elif step[0] == 4: # ENDPOLY
                path_data.append("z")
                currx, curry = 0.0, 0.0

            if step[0] != 4:
                currx, curry = step[-2], -step[-1]
        path_data = ''.join(path_data)
        char_num = 'c_%s' % md5(path_data).hexdigest()
        path_element = '<path id="%s" d="%s"/>\n' % (char_num, ''.join(path_data))
        self._char_defs[char_id] = char_num
        return path_element

    def _get_char_def_id(self, prop, char):
        if isinstance(prop, FontProperties):
            newprop = prop.copy()
            font = self._get_font(newprop)
        else:
            font = prop
        font.set_size(self.FONT_SCALE, 72)
        ps_name = font.get_sfnt()[(1,0,0,6)]
        char_id = urllib.quote('%s-%d' % (ps_name, ord(char)))
        return self._char_defs[char_id]

    def _draw_mathtext(self, gc, x, y, s, prop, angle):
        """
        Draw math text using matplotlib.mathtext
        """
        width, height, descent, svg_elements, used_characters = \
            self.mathtext_parser.parse(s, 72, prop)
        svg_glyphs = svg_elements.svg_glyphs
        svg_rects = svg_elements.svg_rects
        color = rgb2hex(gc.get_rgb())
        write = self._svgwriter.write

        style = "fill: %s" % color

        if rcParams['svg.embed_char_paths']:
            new_chars = []
            for font, fontsize, thetext, new_x, new_y_mtc, metrics in svg_glyphs:
                path = self._add_char_def(font, thetext)
                if path is not None:
                    new_chars.append(path)
            if len(new_chars):
                write('<defs>\n')
                for path in new_chars:
                    write(path)
                write('</defs>\n')

            svg = ['<g style="%s" transform="' % style]
            if angle != 0:
                svg.append('translate(%f,%f)rotate(%1.1f)'
                           % (x,y,-angle) )
            else:
                svg.append('translate(%f,%f)' % (x, y))
            svg.append('">\n')

            for font, fontsize, thetext, new_x, new_y_mtc, metrics in svg_glyphs:
                charid = self._get_char_def_id(font, thetext)

                svg.append('<use xlink:href="#%s" transform="translate(%f,%f)scale(%f)"/>\n' %
                           (charid, new_x, -new_y_mtc, fontsize / self.FONT_SCALE))
            svg.append('</g>\n')
        else: # not rcParams['svg.embed_char_paths']
            svg = ['<text style="%s" x="%f" y="%f"' % (style, x, y)]

            if angle != 0:
                svg.append(' transform="translate(%f,%f) rotate(%1.1f) translate(%f,%f)"'
                           % (x,y,-angle,-x,-y) ) # Inkscape doesn't support rotate(angle x y)
            svg.append('>\n')

            curr_x,curr_y = 0.0,0.0

            for font, fontsize, thetext, new_x, new_y_mtc, metrics in svg_glyphs:
                new_y = - new_y_mtc
                style = "font-size: %f; font-family: %s" % (fontsize, font.family_name)

                svg.append('<tspan style="%s"' % style)
                xadvance = metrics.advance
                svg.append(' textLength="%f"' % xadvance)

                dx = new_x - curr_x
                if dx != 0.0:
                    svg.append(' dx="%f"' % dx)

                dy = new_y - curr_y
                if dy != 0.0:
                    svg.append(' dy="%f"' % dy)

                thetext = escape_xml_text(thetext)

                svg.append('>%s</tspan>\n' % thetext)

                curr_x = new_x + xadvance
                curr_y = new_y

            svg.append('</text>\n')

        if len(svg_rects):
            style = "fill: %s; stroke: none" % color
            svg.append('<g style="%s" transform="' % style)
            if angle != 0:
                svg.append('translate(%f,%f) rotate(%1.1f)'
                           % (x,y,-angle) )
            else:
                svg.append('translate(%f,%f)' % (x, y))
            svg.append('">\n')

            for x, y, width, height in svg_rects:
                svg.append('<rect x="%f" y="%f" width="%f" height="%f" fill="black" stroke="none" />' % (x, -y + height, width, height))
            svg.append("</g>")

        self.open_group("mathtext")
        write (''.join(svg))
        self.close_group("mathtext")

    def finalize(self):
        write = self._svgwriter.write
        write('</svg>\n')

    def flipy(self):
        return True

    def get_canvas_width_height(self):
        return self.width, self.height

    def get_text_width_height_descent(self, s, prop, ismath):
        if rcParams['text.usetex']:
            size = prop.get_size_in_points()
            texmanager = self._text2path.get_texmanager()
            fontsize = prop.get_size_in_points()
            w, h, d = texmanager.get_text_width_height_descent(s, fontsize,
                                                               renderer=self)
            return w, h, d

        if ismath:
            width, height, descent, trash, used_characters = \
                self.mathtext_parser.parse(s, 72, prop)
            return width, height, descent
        font = self._get_font(prop)
        font.set_text(s, 0.0, flags=LOAD_NO_HINTING)
        w, h = font.get_width_height()
        w /= 64.0  # convert from subpixels
        h /= 64.0
        d = font.get_descent()
        d /= 64.0
        return w, h, d


class FigureCanvasSVG(FigureCanvasBase):
    filetypes = {'svg': 'Scalable Vector Graphics',
                 'svgz': 'Scalable Vector Graphics'}

    def print_svg(self, filename, *args, **kwargs):
        if is_string_like(filename):
            fh_to_close = svgwriter = codecs.open(filename, 'w', 'utf-8')
        elif is_writable_file_like(filename):
            svgwriter = codecs.getwriter('utf-8')(filename)
            fh_to_close = None
        else:
            raise ValueError("filename must be a path or a file-like object")
        return self._print_svg(filename, svgwriter, fh_to_close, **kwargs)

    def print_svgz(self, filename, *args, **kwargs):
        if is_string_like(filename):
            gzipwriter = gzip.GzipFile(filename, 'w')
            fh_to_close = svgwriter = codecs.getwriter('utf-8')(gzipwriter)
        elif is_writable_file_like(filename):
            fh_to_close = gzipwriter = gzip.GzipFile(fileobj=filename, mode='w')
            svgwriter = codecs.getwriter('utf-8')(gzipwriter)
        else:
            raise ValueError("filename must be a path or a file-like object")
        return self._print_svg(filename, svgwriter, fh_to_close)

    def _print_svg(self, filename, svgwriter, fh_to_close=None, **kwargs):
        self.figure.set_dpi(72.0)
        width, height = self.figure.get_size_inches()
        w, h = width*72, height*72

        if rcParams['svg.image_noscale']:
            renderer = RendererSVG(w, h, svgwriter, filename)
        else:
            # setting mixed renderer dpi other than 72 results in
            # incorrect size of the rasterized image. It seems that the
            # svg internally uses fixed dpi of 72 and seems to cause
            # the problem. I hope someone who knows the svg backends
            # take a look at this problem. Meanwhile, the dpi
            # parameter is ignored and image_dpi is fixed at 72. - JJL

            #image_dpi = kwargs.pop("dpi", 72)
            image_dpi = 72
            _bbox_inches_restore = kwargs.pop("bbox_inches_restore", None)
            renderer = MixedModeRenderer(self.figure,
                width, height, image_dpi, RendererSVG(w, h, svgwriter, filename),
                bbox_inches_restore=_bbox_inches_restore)

        self.figure.draw(renderer)
        renderer.finalize()
        if fh_to_close is not None:
            svgwriter.close()

    def get_default_filetype(self):
        return 'svg'

class FigureManagerSVG(FigureManagerBase):
    pass

FigureManager = FigureManagerSVG

svgProlog = """\
<?xml version="1.0" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN"
  "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<!-- Created with matplotlib (http://matplotlib.sourceforge.net/) -->
<svg width="%ipt" height="%ipt" viewBox="0 0 %i %i"
   xmlns="http://www.w3.org/2000/svg"
   xmlns:xlink="http://www.w3.org/1999/xlink"
   version="1.1"
   id="svg1">
<filter id="colorAdd"><feComposite in="SourceGraphic" in2="BackgroundImage" operator="arithmetic" k2="1" k3="1"/></filter>
"""
