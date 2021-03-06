""" REPL Console for Inspecting Stack

>>> from rpw.ui.forms import Console
>>> Console()
# Console is launched with locally defined variables injected into context.

Keyboard Shortcuts:
    * ``UP``  Iterate history up
    * ``Down``  Iterate history down
    * ``Tab``  Iterate possible autocomplete options

Note:
    The last stack frame is automatically injected is the context of the evaluation
    loop of the console: the local and global variables from where the Console
    was called from should be available.

    Inspection of the stack requires `stack frames` to be enabled.
    If an exception is raised stating ```object has no attribute '_getframe'``
    it means IronPython stack frames is not enabled.
    You can enable it by running with the ``-X`` argument:
    ``ipy.exe -X: FullFrames file.py``.

    If you are trying to use it from within Dynamo, stack inspection is
    currently not available due to how the engine is setup,
    but you can still use it by manually passing the context you want to inspect:

    >>> Console(context=locals())  # or
    >>> Console(context=globals())

"""  #

import os
import inspect
import logging
import tempfile
from collections import defaultdict

from rpw.ui.forms.resources import Window
from rpw.ui.forms.resources import *
# logger.verbose(True)

class Console(Window):
    LAYOUT = """
                <Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
                        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
                        Title="DeployWindow" Height="400" Width="800" SnapsToDevicePixels="True"
                        UseLayoutRounding="True" WindowState="Normal" WindowStartupLocation="CenterScreen">
                <Window.Resources>
                    <Style TargetType="{x:Type MenuItem}">
                        <Setter Property="FontFamily" Value="Consolas"/>
                        <Setter Property="FontSize" Value="12.0"/>
                    </Style>
                </Window.Resources>
                <Grid>
                    <Grid.ColumnDefinitions>
                        <ColumnDefinition Width="*"></ColumnDefinition>
                    </Grid.ColumnDefinitions>
                <Grid.RowDefinitions>
                    <RowDefinition Height="0"></RowDefinition>
                    <RowDefinition Height="*"></RowDefinition>
                </Grid.RowDefinitions>
                <TextBox Grid.Column="1" Grid.Row="1"  HorizontalAlignment="Stretch"
                         Name="tbox" Margin="6,6,6,6" VerticalAlignment="Stretch"
                         AcceptsReturn="True" VerticalScrollBarVisibility="Auto"
                         TextWrapping="Wrap"
                         FontFamily="Consolas" FontSize="12.0"
                         />
                </Grid>
                </Window>
    """
    # <Button Grid.Column="1" Content="Deploy" Height="30" Width="100" HorizontalAlignment="Left" Margin="10,10,10,10" Name="deployButton" Cursor="Hand" />

    CARET = '>>> '

    def __init__(self, stack_level=1, stack_info=True, context=None):
        """
        Args:
            stack_level (int): Default is 1. 0 Is the Console stack, 1 is the
                               caller; 2 is previous to that, etc.
            stack_info (bool): Display info about where call came from.
                               Will print filename name,  line no. and Caller
                               name.
            context (dict): Optional Dictionary for when inspection is not
                            possible.
        """

        # History Helper
        tempdir = tempfile.gettempdir()
        filename = 'rpw-history'
        self.history_file = os.path.join(tempdir, filename)

        self.stack_locals = {}
        self.stack_globals = {}
        self.stack_level = stack_level

        if context:
            self.stack_locals.update(context)
            # Allows to pass context manually, so it can be used in Dynamo
            # Where inspection does not work
        else:
            # Stack Info
            # stack_frame = inspect.currentframe().f_back
            stack_frame = inspect.stack()[stack_level][0] # Finds Calling Stack

            self.stack_locals.update(stack_frame.f_locals)
            self.stack_globals.update(stack_frame.f_globals)
            # Debug Console
            self.stack_globals.update({'stack': inspect.stack()})

            stack_code = stack_frame.f_code
            stack_filename = os.path.basename(stack_code.co_filename)
            stack_lineno = stack_code.co_firstlineno
            stack_caller = stack_code.co_name

        # Form Setup
        self.ui = wpf.LoadComponent(self, StringReader(Console.LAYOUT))
        self.ui.Title = 'RevitPythonWrapper Console'
        self.PreviewKeyDown += self.KeyPressPreview
        self.KeyUp += self.OnKeyUpHandler
        self.is_loaded = False

        # Form Init
        self.ui.tbox.Focus()
        if not context and stack_info:
            self.write_line('Caller: {} [ Line:{}] | File: {}'.format(stack_caller, stack_lineno, stack_filename))
        else:
            self.tbox.Text = Console.CARET

        self.ui.tbox.CaretIndex = len(self.tbox.Text)

        # Vars
        self.history_index = 0
        self.ac_options = defaultdict(int)

        self.ShowDialog()

    def get_line(self, index):
        line = self.tbox.GetLineText(index).replace('\r\n','')
        if line.startswith(Console.CARET):
            line = line[len(Console.CARET):]
        logger.debug('Get Line: {}'.format(line))
        return line

    def get_last_line(self):
        try:
            last_line = self.get_lines()[-1]
        except IndexError:
            last_line = self.get_line(0)
        logger.debug('Last Line: {}'.format(last_line))
        return last_line

    def get_last_entered_line(self):
        try:
            last_line = self.get_lines()[-2]
        except IndexError:
            last_line = self.get_line(0)
        logger.debug('Last Line: {}'.format(last_line))
        return last_line

    def get_lines(self):
        last_line_index = self.tbox.LineCount
        lines = []
        for index in range(0, last_line_index):
            line = self.get_line(index)
            lines.append(line)
        logger.debug('Lines: {}'.format(lines))
        return lines

    def OnKeyUpHandler(self, sender, args):
        # Need to use this to be able to override ENTER
        if not self.is_loaded:
            return
        if args.Key == Key.Enter:
            entered_line = self.get_last_entered_line()
            if entered_line == '':
                self.write_line(None)
                return
            output = self.evaluate(entered_line)
            self.append_history(entered_line)
            self.history_index = 0
            self.write_line(output)

    def evaluate(self, line):
        try:
            output = eval(line, self.stack_globals, self.stack_locals)
        except SyntaxError as errmsg:
            try:
                exec(line, self.stack_globals, self.stack_locals)
                return
            except Exception as errmsg:
                output = errmsg
        except Exception as errmsg:
            output = errmsg
        return str(output)

    def OnKeyDownHandler(self, sender, args):
        pass

    def reset_caret(self):
        self.tbox.CaretIndex = self.tbox.Text.rfind(Console.CARET) + len(Console.CARET)

    def KeyPressPreview(self, sender, e):
        # This Happens before all other key handlers
        # If e.Handled = True, stops event propagation here.
        e.Handled = False
        if self.tbox.CaretIndex < self.tbox.Text.rfind(Console.CARET):
            self.tbox.CaretIndex = len(self.tbox.Text)
        if e.Key == Key.Up:
            self.history_up()
            e.Handled = True
        if e.Key == Key.Down:
            self.history_down()
            e.Handled = True
        if e.Key == Key.Left or e.Key == Key.Back:
            if self.ui.tbox.CaretIndex == self.tbox.Text.rfind(Console.CARET) + len(Console.CARET):
                e.Handled = True
        if e.Key == Key.Home:
            self.reset_caret()
            e.Handled = True
        if e.Key == Key.Tab:
            self.autocomplete()
            e.Handled = True
        if e.Key == Key.Enter:
            self.is_loaded = True
            self.tbox.CaretIndex = len(self.tbox.Text)


    def autocomplete(self):
        # TODO: Add recursive dir() attribute suggestions

        last_line = self.get_last_line()
        cursor_line_index = self.tbox.CaretIndex - self.tbox.Text.rfind(Console.CARET) - len(Console.CARET)
        text = last_line[0:cursor_line_index]
        possibilities = set(self.stack_locals.keys() +
                            self.stack_globals.keys() +
                            ['locals', 'globals', 'vars'] +
                            self.get_all_history()[::-1][0:20] # Last 20 cmds
                            )
        suggestions = [p for p in possibilities if p.lower().startswith(text.lower())]

        logger.debug('Text: {}'.format(text))
        logger.debug('Sug: {}'.format(suggestions))

        if not suggestions:
            return None
        # Create Dictionary to Track iteration over suggestion
        index = self.ac_options[text]
        try:
            suggestion = suggestions[index]
        except IndexError:
            self.ac_options[text] = 0
            suggestion = suggestions[0]
        self.ac_options[text] += 1

        if suggestion is not None:
            caret_index = self.tbox.CaretIndex
            self.write_text(suggestion)
            self.tbox.CaretIndex = caret_index

    def write_line(self, line=None):
        # Used for Code Output
        # Writes line with no starting caret, new line + caret
        if line:
            self.tbox.AppendText(line)
            self.tbox.AppendText(NewLine)
        self.tbox.AppendText(Console.CARET)

    def write_text(self, line):
        # Used by Autocomplete and History
        # Adds text to line, including Caret
        last_new_line = self.tbox.Text.rfind(Console.CARET)
        self.tbox.Text = self.tbox.Text[0:last_new_line]
        self.tbox.AppendText(Console.CARET)
        self.tbox.AppendText(line)
        self.ui.tbox.CaretIndex = len(self.ui.tbox.Text)

    def get_all_history(self):
        # TODO: Add clean up when history > X
        with open(self.history_file) as fp:
            lines = [l for l in fp.read().split('\n') if l != '']
            return lines

    def history_up(self):
        self.history_index += 1
        line = self.history_iter()
        if line is not None:
            self.write_text(line)

    def history_down(self):
        self.history_index -= 1
        line = self.history_iter()
        if line is not None:
            self.write_text(line)

    def append_history(self, line):
        logger.debug('Adding Line to History:' + repr(line))
        with open(self.history_file, 'a') as fp:
            fp.write(line + '\n')

    def history_iter(self):
        lines = self.get_all_history()
        logger.debug('Lines: {}'.format(lines))
        try:
            line = lines[::-1][self.history_index -1]
        # Wrap around lines to loop and up down infinetly.
        except IndexError:
            if len(lines) == 0:
                return None
            if len(lines) < 0:
                self.history_index += len(lines)
            if len(lines) > 0:
                self.history_index -= len(lines)
            line = lines[0]
        return line

    def __repr__(self):
        '<rpw:Console stack_level={}>'.format(self.stack_level)


if __name__ == '__main__':
    def test():
        x = 1
        # Console()
        Console(context=locals())
    test()
    z =2
