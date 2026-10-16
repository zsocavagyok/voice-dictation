"""Draws the app icon (a microphone on a rounded square) as a 1024px PNG."""
import sys

from AppKit import (NSBezierPath, NSBitmapImageRep, NSColor, NSFont,
                    NSFontAttributeName, NSGradient, NSImage,
                    NSPNGFileType, NSString)
from Foundation import NSMakeRect, NSMakeSize

SIZE = 1024
image = NSImage.alloc().initWithSize_(NSMakeSize(SIZE, SIZE))
image.lockFocus()

inset = SIZE * 0.1
rect = NSMakeRect(inset, inset, SIZE - 2 * inset, SIZE - 2 * inset)
path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, 185, 185)
NSGradient.alloc().initWithStartingColor_endingColor_(
    NSColor.colorWithSRGBRed_green_blue_alpha_(0.33, 0.42, 0.98, 1),
    NSColor.colorWithSRGBRed_green_blue_alpha_(0.58, 0.29, 0.92, 1),
).drawInBezierPath_angle_(path, -90)

mic = NSString.stringWithString_("🎙")
attrs = {NSFontAttributeName: NSFont.systemFontOfSize_(520)}
w, h = mic.sizeWithAttributes_(attrs)
mic.drawAtPoint_withAttributes_(((SIZE - w) / 2, (SIZE - h) / 2), attrs)

image.unlockFocus()
rep = NSBitmapImageRep.imageRepWithData_(image.TIFFRepresentation())
rep.representationUsingType_properties_(NSPNGFileType, None).writeToFile_atomically_(
    sys.argv[1], True
)
