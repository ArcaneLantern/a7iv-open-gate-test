# A7 IV open gate: field test kit
<br />



  [![Discord Server](https://discord.com/api/guilds/1572476739429597224/widget.png?style=banner2)](https://discord.gg/YPPTm44rz)
<br />
<p>For the Sony A7 IV on firmware 6.02. Writes <b>temporary settings</b> into the camera's memory <b>only</b>; a cold boot (battery out for a few seconds) returns it to stock.</p>

<p>This may also return to stock if you turn the camerra off for more than a few seconds without pulling the battery. If you want to record open gate out in the field, use the Android version to setup the camera before you shoot</p>

<p>android/A7IV-OpenGate.apk: the phone app (USB-C to the camera) both 4K and 5.7K options.<br />
windows/open_gate_4k.cmd: 4K open gate, 3840x2560, rear screen 3:2, C3 de-squeeze preview cycle.<br />
windows/open_gate_5.7k.cmd: 5.7K open gate, 5760x3840, rear screen 3:2, C3 de-squeeze preview cycle.<br />
macos/open_gate_4k.command and macos/open_gate_5.7k.command: the same two, on a Mac.</p>
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



<h3>macOS</h3>
<p>No driver or Zadig step is needed on a Mac. You need Python 3.9 or later: the one macOS offers with the Xcode Command Line Tools (run <em>xcode-select --install</em> in Terminal) works, or install it from python.org.</p>

<p>Once: double-click "macos/setup.command". It sets up Python and the USB library the scripts use (no Homebrew needed).</p>

<p>Then connect the camera like on Windows (stills dial, USB Connection Mode: Mass Storage, select "Image Transfer (MSC)") and double-click "macos/open_gate_4k.command" or "macos/open_gate_5.7k.command".</p>

<p>The script asks for your Mac password. macOS keeps its own driver on the camera's USB connection, and only an administrator can hand the camera over to the script. The script unmounts the camera's memory card first; it does not erase anything on it.</p>

<p>If macOS refuses to open a .command file ("unidentified developer" or "could not verify"), open System Settings &gt; Privacy &amp; Security, scroll down and click "Open Anyway" (it shows for about an hour after the refusal). Or open Terminal, type <em>bash</em> and a space, drag the .command file into the window, and press Return.</p>

<p>Just like with Windows, you'll need to re-enter "Image Transfer (MSC)" several times. Press the circle button on the back whenever that pops up.</p>



<h3>Android</h3>

<p>You need a USB C to C cable and a phone/device that supports OTG. Install the app. Open it, turn the camera to stills dial, connect it, turn it on, select "Image Transfer (MSC)", select your options and tap "Apply to camera"</p>

<p>Just like with the Windows version you'll need to re-enter "Image Transfer (MSC)" several times. Press the circle button on the back whenever that pops up.</p>

<img width="1216" height="2640" alt="10269" src="https://github.com/user-attachments/assets/21ed1586-602f-4396-8811-f7f2a147398e" />


<h3>Can I support the project?</h3>
Yes, I currently accept donations at: https://ko-fi.com/arcanelantern<br />
If you decide to donate, please leave a message about what you are most interested in (feature, camera model etc).<br />
<p>I could also use donated camera time testing patches for cameras I do not currently possess</p>
<p></p>

<h3>Special Thanks</h3>
<p><b><a href="https://github.com/Erlla/sony-a7m4-custom-firmware">Erlla/sony-a7m4-custom-firmware</a></b><br />
It showed that a normal USB cable could run native code on the A7iv through the service protocol</p>

<p><b><a href="https://github.com/ma1co/Sony-PMCA-RE">ma1co/Sony-PMCA-RE</a></b><br />
It handles the switch from mass storage mode to service mode</p>

<p><b><a href="https://github.com/DavidBuchanan314/fwtool.py">DavidBuchanan314/fwtool.py</a></b><br />
It unpacks the firmware files needed for analysing<br />
It is a fork of <a href="https://github.com/ma1co/fwtool.py">ma1co/fwtool.py</a>, which deserves credit too</p>

<p><b><a href="https://github.com/leogenot/sony-a7iv-feature-research">leogenot/sony-a7iv-feature-research</a></b><br />
Documented the exact working service mode routine on the A7iv</p>

