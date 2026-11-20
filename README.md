# A7 IV open gate: field test kit
<br />



  [![Discord Server](https://discord.com/api/guilds/1572476739429597224/widget.png?style=banner2)](https://discord.gg/YPPTm44rz)
<br />
<p>For the Sony A7 IV on firmware 6.02. Writes <b>temporary settings</b> into the camera's memory <b>only</b>; a cold boot (battery out for a few seconds) returns it to stock.</p>

<p>This may also return to stock if you turn the camerra off for more than a few seconds without pulling the battery. If you want to record open gate out in the field, use the Android version to setup the camera before you shoot</p>

<p>android/A7IV-OpenGate.apk: the phone app (USB-C to the camera) both 4K and 5.7K options.<br />
windows/open_gate_4k.cmd: 4K open gate, 3840x2560, rear screen 3:2, C3 de-squeeze preview cycle.<br />
windows/open_gate_5.7k.cmd: 5.7K open gate, 5760x3840, rear screen 3:2, C3 de-squeeze preview cycle.</p>
<h3>Issues</h3>
<ul>
  <li>5.7K does not currently play back in camera</li>
  <li>5.7K is still set at 100mbps, this will change in an update as it needs more</li>
  <li>You may need to use ffmpeg to correct clips to use in Davinci resolve or other editors, they work correctly in VLC, but may appear vertically squeezed (4K 3:2) or garbled (5.7K), the command for this is:<br />
  <em>ffmpeg -i input.mp4 -map 0:v:0 -map 0:a? -c copy -movflags +faststart output_fixed.mp4</em>
  </li>
</ul>


<h3>Windows</h3>
<p>Windows, once: run "windows/setup.cmd", then install the libusb-win32 driver for the camera with Zadig (camera on, USB Connection Mode: Mass Storage; again once it has switched to service mode).</p>


<p>You can install this from a Windows PC or an Android phone/device that supports OTG.</p>

<p>If using Windows you must install Zadig, connect your A7iv via USB cable to the PC, select "Image Transfer (MSC)"</p>

<p>You will also need to install Python 3 on your system.</p>

<p>Inside Zadig select list devices so its ticked, untick and re-tick if necessary, select the camera (probably ILCE-7M4) and replace the driver with libusb32. Once that is done the install scripts will work.</p>

<p>Open up a CMD Window, run setup, then ren which ever open gate version you want.</p>

<p>Currently they both use 100mbps stock at the moment which needs to be increased for 5.7K.</p>

<p>You will need to re-enter "Image Transfer (MSC)" multiple times until the script is finished, just push the circle button on the back of the camera each time it comes back up until it's complete.</p>



<h3>Android</h3>

<p>You need a USB C to C cable and a phone/device that supports OTG. Install the app. Open it, turn the camera to stills dial, connect it, turn it on, select "Image Transfer (MSC)", select your options and tap "Apply to camera"</p>

<p>Just like with the Windows version you'll need to re-enter "Image Transfer (MSC)" several times. Press the circle button on the back whenever that pops up.</p>

<img width="1216" height="2640" alt="10269" src="https://github.com/user-attachments/assets/21ed1586-602f-4396-8811-f7f2a147398e" />


<h3>Can I support the project?</h3>
Yes, I currently accept donations at: https://ko-fi.com/arcanelantern<br />
If you decide to donate, please leave a message about what you are most interested in (feature, camera model etc).<br />
<p>I could also use donated camera time testing patches for cameras I do not currently possess</p>
<p></p>
