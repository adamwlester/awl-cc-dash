<#
  win-window.ps1 — Win32 window helper for the ui-verify launcher.

  Pushes a Playwright-launched Chromium window to the BOTTOM of the z-order
  WITHOUT activating it (so it never steals foreground), and can restore the
  caller's previous foreground window. All work is done with plain user32
  P/Invoke — no installs, no modules. Windows PowerShell 5.1 compatible.

  Commands (emit one compact JSON line on stdout):
    foreground              -> { foreground: <hwnd> }                 current foreground window
    find    -TargetPid <n>  -> { hwnds: [..] }                        visible top-level Chromium windows for a pid
    park    -TargetPid <n> [-RestoreHwnd <hwnd>]
                            -> { hwnds, foregroundBefore, foregroundAfter }
                               send window(s) to back, no-activate, optionally restore prior foreground
    front   -TargetPid <n>  -> { hwnds, foregroundAfter }             raise + activate (reference "normal headed" mode)

  NOTE: -TargetPid (not -Pid): $PID is a PowerShell automatic variable.
#>
param(
  [Parameter(Mandatory = $true)][ValidateSet('foreground', 'find', 'park', 'front')][string]$Command,
  [int]$TargetPid = 0,
  [long]$RestoreHwnd = 0,
  [int]$TimeoutMs = 4000
)
$ErrorActionPreference = 'Stop'

Add-Type -Language CSharp -TypeDefinition @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class WinWin {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();

  public static readonly IntPtr HWND_TOP    = new IntPtr(0);
  public static readonly IntPtr HWND_BOTTOM = new IntPtr(1);
  public const uint SWP_NOSIZE=0x1, SWP_NOMOVE=0x2, SWP_NOACTIVATE=0x10, SWP_NOOWNERZORDER=0x200;
  public const int SW_SHOWNOACTIVATE=4, SW_SHOW=5;

  public static List<long> Find(uint pid) {
    var found = new List<long>();
    EnumWindows((h, l) => {
      uint wp; GetWindowThreadProcessId(h, out wp);
      if (wp == pid && IsWindowVisible(h)) {
        var cn = new StringBuilder(256); GetClassName(h, cn, 256);
        if (cn.ToString().StartsWith("Chrome_WidgetWin")) {
          var tt = new StringBuilder(256); GetWindowText(h, tt, 256);
          if (tt.Length > 0) found.Add(h.ToInt64());
        }
      }
      return true;
    }, IntPtr.Zero);
    return found;
  }
}
"@

function Get-Fg { return [WinWin]::GetForegroundWindow().ToInt64() }

function Find-Windows([int]$p) {
  $deadline = [Environment]::TickCount + $TimeoutMs
  do {
    $hs = [WinWin]::Find([uint32]$p)
    if ($hs.Count -gt 0) { return $hs }
    Start-Sleep -Milliseconds 120
  } while ([Environment]::TickCount -lt $deadline)
  return $hs
}

$result = @{ command = $Command; targetPid = $TargetPid }

switch ($Command) {
  'foreground' {
    $result.foreground = Get-Fg
  }
  'find' {
    $result.hwnds = @(Find-Windows $TargetPid)
  }
  'park' {
    $result.foregroundBefore = Get-Fg
    $hs = Find-Windows $TargetPid
    $result.hwnds = @($hs)
    $parkFlags = ([WinWin]::SWP_NOSIZE -bor [WinWin]::SWP_NOMOVE -bor [WinWin]::SWP_NOACTIVATE -bor [WinWin]::SWP_NOOWNERZORDER)
    foreach ($h in $hs) {
      $hp = [IntPtr]::new([long]$h)
      [void][WinWin]::SetWindowPos($hp, [WinWin]::HWND_BOTTOM, 0, 0, 0, 0, $parkFlags)
      [void][WinWin]::ShowWindowAsync($hp, [WinWin]::SW_SHOWNOACTIVATE)
    }
    if ($RestoreHwnd -ne 0) {
      [void][WinWin]::SetForegroundWindow([IntPtr]::new($RestoreHwnd))
    }
    Start-Sleep -Milliseconds 80
    $result.foregroundAfter = Get-Fg
  }
  'front' {
    $hs = Find-Windows $TargetPid
    $result.hwnds = @($hs)
    foreach ($h in $hs) {
      $hp = [IntPtr]::new([long]$h)
      [void][WinWin]::SetWindowPos($hp, [WinWin]::HWND_TOP, 0, 0, 0, 0, ([WinWin]::SWP_NOSIZE -bor [WinWin]::SWP_NOMOVE))
      [void][WinWin]::ShowWindowAsync($hp, [WinWin]::SW_SHOW)
      [void][WinWin]::SetForegroundWindow($hp)
    }
    Start-Sleep -Milliseconds 80
    $result.foregroundAfter = Get-Fg
  }
}

$result | ConvertTo-Json -Compress
